# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import math
import os
import pathlib
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from .a2ui_utils import a2ui_callback

load_dotenv()

PROJECT_ID = "qwiklabs-gcp-02-a4a086486940"
BUCKET_NAME = "fitcoach-ai-media-qwiklabs-gcp-02-a4a086486940"
MEMORY_BANK_ID = "5078296213267152896"

a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description="You are FitCoach AI, an intelligent fitness assistant that helps users plan workouts, generate workout motivational visuals, find nearby gyms and workout spots, track training progress, look up exercises in the wger exercise library, find tailored workout plans from Firestore, run Python code safely in a sandbox, and remember user facts and preferences across sessions.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property (\'h1\', \'h2\', \'body\') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


# Memory generation callback for durable fact extraction across sessions
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


def memory_service_builder():
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-central1",
        agent_engine_id=MEMORY_BANK_ID,
    )

# Load Agent Engine sandbox metadata if available
_meta_path = pathlib.Path(__file__).parent.parent / "deployment_metadata.json"
_remote_agent_id = None
_sandbox_id = None

if _meta_path.exists():
    try:
        with open(_meta_path) as _f:
            _meta = json.load(_f)
            _remote_agent_id = _meta.get("remote_agent_runtime_id")
            _sandbox_id = _meta.get("sandbox_resource_name")
    except Exception:
        pass

if _sandbox_id:
    code_executor = AgentEngineSandboxCodeExecutor(sandbox_resource_name=_sandbox_id)
elif _remote_agent_id:
    code_executor = AgentEngineSandboxCodeExecutor(agent_engine_resource_name=_remote_agent_id)
else:
    code_executor = AgentEngineSandboxCodeExecutor()


async def generate_workout_visual(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates a fitness/workout visual using Gemini 3.1 Flash Lite Image model, saves it as an artifact, uploads it to Cloud Storage, and returns its public URL.

    Args:
        prompt: Description of the workout or fitness visual to generate (e.g. 'Runner crossing finish line at sunrise').
        tool_context: ToolContext object passed automatically by ADK.

    Returns:
        The public HTTPS URL of the generated image.
    """
    try:
        genai_client = genai.Client(vertexai=True, location="global")
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return "Failed to generate image bytes from model response."

        filename = f"visual_{uuid.uuid4().hex[:8]}.jpg"

        # 1. Save artifact if tool_context is provided
        if tool_context:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload same image bytes to public Cloud Storage bucket
        gcs_client = storage.Client(project=PROJECT_ID)
        bucket = gcs_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return f"Successfully generated workout visual!\nPublic Image URL: {public_url}"
    except Exception as err:
        return f"Error generating or uploading workout visual: {err}"


async def generate_workout_video(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates a short fitness/workout demonstration video using Google Gemini Omni model (gemini-omni-flash-preview) in the global region, saves it as an artifact, uploads it to Cloud Storage, and returns its public URL.

    Args:
        prompt: Description of the fitness exercise or workout video to generate (e.g. 'A short video demonstration of a athlete performing kettlebell swings').
        tool_context: ToolContext object passed automatically by ADK.

    Returns:
        The public HTTPS URL of the generated video.
    """
    try:
        genai_client = genai.Client(vertexai=True, location="global")
        response = genai_client.models.generate_content(
            model="gemini-omni-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["VIDEO"]),
        )

        video_bytes = None
        mime_type = "video/mp4"
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    video_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "video/mp4"
                    break

        if not video_bytes:
            return "Failed to generate video bytes from model response."

        filename = f"video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save artifact if tool_context is provided
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload same video bytes directly to public Cloud Storage bucket
        gcs_client = storage.Client(project=PROJECT_ID)
        bucket = gcs_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return f"Successfully generated workout video!\nPublic Video URL: {public_url}"
    except Exception as err:
        return f"Error generating or uploading workout video: {err}"


def geocode_address(address: str) -> str:
    """Converts a street address or city name into geographic coordinates (latitude and longitude) using Google Geocoding API.

    Args:
        address: The street address or city name, e.g. 'San Francisco, CA' or '1600 Amphitheatre Pkwy, Mountain View, CA'.

    Returns:
        Formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in .env."

    encoded_addr = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FitCoachAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for address '{address}': {data.get('status', 'No results')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address")
        location = result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return f"Geocoded Address: {formatted_address}\nLocation: Latitude {lat}, Longitude {lng}"
    except Exception as err:
        return f"Error calling Geocoding API: {err}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "gym", radius_meters: float = 3000.0) -> str:
    """Finds nearby places of a given type around coordinates using Google Places API (New).

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        place_type: Type of place, e.g. 'gym', 'park', 'fitness_center', 'sports_complex'.
        radius_meters: Search radius in meters (default 3000m).

    Returns:
        List of nearby places with name, formatted address, and coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in .env."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby '{place_type}' places found within {radius_meters}m of ({latitude}, {longitude})."

        results = []
        for p in places:
            name = p.get("displayName", {}).get("text", "Unknown Place")
            addr = p.get("formattedAddress", "No address")
            loc = p.get("location", {})
            results.append(
                f"- **{name}**: {addr} (Lat: {loc.get('latitude')}, Lng: {loc.get('longitude')})"
            )

        return f"Nearby Places ({len(results)} found):\n" + "\n".join(results)
    except Exception as err:
        return f"Error calling Places API (New): {err}"


def search_exercise_library(query: str = "") -> str:
    """Searches the open-source wger Workout Manager exercise database for exercises, equipment, and muscle targets.

    Args:
        query: Optional search term, e.g. 'kettlebell', 'swing', 'squat', 'bench', 'abs', 'legs'.

    Returns:
        A list of matching exercises with equipment and target muscle details.
    """
    url = "https://wger.de/api/v2/exerciseinfo/?limit=20"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FitCoachAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        results = []
        q = query.lower().strip()
        for item in data.get("results", []):
            category = item.get("category", {}).get("name", "General")
            equipment = ", ".join(
                [eq.get("name") for eq in item.get("equipment", [])]
            ) or "Bodyweight"
            muscles = ", ".join(
                [m.get("name_en", m.get("name")) for m in item.get("muscles", [])]
            ) or "Full Body"

            for t in item.get("translations", []):
                name = t.get("name")
                desc = t.get("description", "").replace("<p>", "").replace("</p>", "").strip()
                if not name:
                    continue
                if not q or q in name.lower() or q in category.lower() or q in muscles.lower() or q in equipment.lower():
                    results.append(
                        f"- **{name}** (Category: {category} | Equipment: {equipment} | Muscles: {muscles})"
                    )

        if not results:
            return f"No exercises matching '{query}' were found in the wger database."

        return f"Wger Exercise Database Results ({len(results[:5])} items):\n" + "\n".join(results[:5])
    except Exception as err:
        return f"Error querying wger exercise database: {err}"


def list_workout_plans(category: str = None) -> str:
    """Retrieves available workout plans from the Firestore database, optionally filtered by category.

    Args:
        category: Optional workout category filter (e.g. 'Running', 'HIIT', 'Strength', 'Cycling', 'Recovery').

    Returns:
        A list of matching workout plans with details.
    """
    try:
        db = firestore.Client(project=PROJECT_ID)
        col_ref = db.collection("workout_plans")
        if category:
            docs = col_ref.where("category", "==", category).stream()
        else:
            docs = col_ref.stream()

        plans = []
        for doc in docs:
            data = doc.to_dict()
            plans.append(
                f"- [{data.get('id')}] {data.get('title')} ({data.get('category')} | {data.get('difficulty')}): "
                f"{data.get('duration_mins')} mins, Target HR: {data.get('target_hr_zone')}, "
                f"Est Burn: {data.get('calories_burn_est')} kcal. Description: {data.get('description')}"
            )

        if not plans:
            return f"No workout plans found for category '{category}'." if category else "No workout plans found in database."

        return f"Found {len(plans)} workout plan(s):\n" + "\n".join(plans)
    except Exception as err:
        return f"Error querying Firestore workout plans: {err}"


def calculate(expression: str) -> str:
    """Evaluates a mathematical expression safely.

    Args:
        expression: A math expression string, e.g. '15 * 8 + 42' or 'sqrt(144)'.

    Returns:
        Result of the mathematical calculation.
    """
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "pi": math.pi,
        "e": math.e,
    }
    try:
        # Safe eval using limited globals/locals
        res = eval(expression, {"__builtins__": None}, allowed_names)
        return f"Calculation result: {res}"
    except Exception as err:
        return f"Error calculating expression '{expression}': {err}"


def convert_currency(amount: float, from_curr: str, to_curr: str) -> str:
    """Converts money between major currencies.

    Args:
        amount: The monetary amount to convert.
        from_curr: The source 3-letter currency code (e.g. USD, EUR, JPY, GBP).
        to_curr: The target 3-letter currency code (e.g. USD, EUR, JPY, GBP).

    Returns:
        A string with the converted currency amount.
    """
    rates = {
        ("USD", "EUR"): 0.92,
        ("EUR", "USD"): 1.09,
        ("USD", "JPY"): 155.0,
        ("JPY", "USD"): 0.0065,
        ("USD", "GBP"): 0.79,
        ("GBP", "USD"): 1.27,
        ("EUR", "GBP"): 0.86,
        ("GBP", "EUR"): 1.16,
    }
    pair = (from_curr.upper(), to_curr.upper())
    if pair in rates:
        converted = amount * rates[pair]
        return f"{amount:.2f} {from_curr.upper()} = {converted:.2f} {to_curr.upper()}"
    elif from_curr.upper() == to_curr.upper():
        return f"{amount:.2f} {from_curr.upper()}"
    else:
        # Fallback simulation
        return f"{amount:.2f} {from_curr.upper()} is approximately {amount * 1.1:.2f} {to_curr.upper()} (simulated rate)."


def get_weather(query: str) -> str:
    """Simulates getting weather information for a location.

    Args:
        query: The location to get weather for.

    Returns:
        Weather report for the location.
    """
    q = query.lower()
    if "sf" in q or "san francisco" in q:
        return "It's 60°F and foggy."
    elif "tokyo" in q:
        return "It's 22°C and clear."
    elif "london" in q:
        return "It's 18°C with light rain."
    return f"Weather for {query}: 72°F and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: City name.

    Returns:
        Formatted time string.
    """
    q = query.lower()
    if "sf" in q or "san francisco" in q:
        tz_name = "America/Los_Angeles"
    elif "tokyo" in q:
        tz_name = "Asia/Tokyo"
    elif "london" in q:
        tz_name = "Europe/London"
    else:
        tz_name = "UTC"

    tz = ZoneInfo(tz_name)
    now = datetime.datetime.now(tz)
    return f"Current time in {query} ({tz_name}): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        generate_workout_visual,
        generate_workout_video,
        geocode_address,
        find_nearby_places,
        search_exercise_library,
        list_workout_plans,
        calculate,
        convert_currency,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)

