import json
from langsmith import traceable
from typing import AsyncGenerator

import google.genai as genai
import httpx
from google.genai import types as genai_types

from app.services.llm import (
    GEMINI_TEXT_MODEL,
    GROQ_AGENT_MODEL,
    get_groq_client,
    get_openai_client,
    sanitize_output,
    settings,
)
from app.services.weather import get_location_from_ip, get_weather_data

WEATHER_SYSTEM_PROMPT = """
You are a professional Weather Assistant. 

### RESPONSE STRUCTURE
Follow this exact order and format for every response:

1. **Answer**: Start with a friendly, direct answer to the user's specific question.
2. **Summary**:
   - Location: **{location_name}**
   - Temperature: **{temp_c}°C**
   - Humidity: **{humidity}%**
   - Condition: **{condition}**
   - Wind Speed: **{wind_speed_kmh} km/h**
3. **Recommendations**: Use a bulleted list (•) to suggest clothing or activities based on current conditions.
4. **Visual Card**: At the very end, append the JSON block below.



### RULES
- **CRITICAL: NEVER output internal monologue, confirmation of tool calls, or "I need to call an API".**
- **CRITICAL: Start your response immediately with section "1. Answer".**
- **CRITICAL: In the JSON block, values must be raw numbers/text ONLY (NO bolding, NO units like km/h or %).**
- Use exactly **two newlines** between each section.
- Use **Bold Text** for all values and headers in the TEXT sections (1, 2, 3).
- Never mention latitude or longitude coordinates.

JSON BLOCK TEMPLATE:
```weather-card
{
  "temp_c": "28",
  "condition": "Cloudy",
  "location": "Indore, India",
  "sunrise": "06:12 AM",
  "sunset": "06:45 PM",
  "humidity": "43",
  "wind": "11",
  "precip": "0.0",
  "rain_chance": "0"
}
```


### EXECUTION STEPS
1. If GPS context (Lat/Lon) is provided, call 'get_weather' immediately.
2. Otherwise, call 'get_current_location' first.
"""


def get_agent_client():
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options={"api_version": "v1beta"},
    )

@traceable(run_type="chain", name="Weather Agent")
async def run_weather_agent_stream(question: str, history: list = None, provider: str = "gemini", user_ip: str = None, lat: float = None, lon: float = None) -> AsyncGenerator[str, None]:
    """
    Main entry point for the weather agent. Dispatches to the correct provider.
    """
    if provider == "gemini":
        async for chunk in _run_gemini_weather_agent(question, history, user_ip, lat, lon):
            yield chunk
    elif provider == "groq":
        async for chunk in _run_groq_weather_agent(question, history, user_ip, lat, lon):
            yield chunk
    elif provider == "ollama":
        async for chunk in _run_ollama_weather_agent(question, history, user_ip, lat, lon):
            yield chunk
    elif provider == "openai":
        async for chunk in _run_openai_weather_agent(question, history, user_ip, lat, lon):
            yield chunk
    else:
        yield f"Weather Agent is not yet supported for provider '{provider}'. Please switch to Gemini or Groq."

async def _run_gemini_weather_agent(question: str, history: list = None, user_ip: str = None, lat: float = None, lon: float = None) -> AsyncGenerator[str, None]:
    """Gemini-specific agent implementation."""
    client = get_agent_client()
    if not client:
        yield "Gemini API key is not configured."
        return

    contents = []
    if history:
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(genai_types.Content(role=role, parts=[genai_types.Part(text=msg["content"])]))
    
    
    full_prompt = question
    if lat is not None and lon is not None:
        full_prompt = f"[GPS CONTEXT: Lat {lat}, Lon {lon}] {question}"
    
    contents.append(genai_types.Content(role="user", parts=[genai_types.Part(text=full_prompt)]))

    get_current_location_decl = genai_types.FunctionDeclaration(
        name="get_current_location",
        description="Get the user's current latitude and longitude based on their IP.",
        parameters={"type": "OBJECT", "properties": {}, "required": []}
    )
    
    get_weather_decl = genai_types.FunctionDeclaration(
        name="get_weather",
        description="Get current weather data for a specific latitude and longitude.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "lat": {"type": "NUMBER", "description": "Latitude"},
                "lon": {"type": "NUMBER", "description": "Longitude"}
            },
            "required": ["lat", "lon"]
        }
    )

    tools = [genai_types.Tool(function_declarations=[get_current_location_decl, get_weather_decl])]
    config = genai_types.GenerateContentConfig(
        system_instruction=WEATHER_SYSTEM_PROMPT,
        tools=tools
    )

    try:
        response = client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=contents, config=config)
        curr_response = response
        
        max_iterations = 5
        for _ in range(max_iterations):
            tool_calls = []
            if curr_response.candidates and curr_response.candidates[0].content.parts:
                for part in curr_response.candidates[0].content.parts:
                    if part.function_call:
                        tool_calls.append(part.function_call)

            if not tool_calls:
                text = curr_response.text
                if text:
                    clean_text = sanitize_output(text)
                    if clean_text: yield clean_text
                break

            contents.append(curr_response.candidates[0].content)

            for call in tool_calls:
                fn_name, args = call.name, call.args
                print(f"[agent-gemini] Calling tool: {fn_name}")
                
                # Pre-lookup city hint for better accuracy (e.g. Indore instead of Ujjain)
                city_hint = None
                if user_ip:
                    ip_loc = await get_location_from_ip(user_ip)
                    city_hint = ip_loc.get("city")

                result = {}
                if fn_name == "get_current_location":
                    if lat is not None and lon is not None:
                        # Use provided GPS data instead of IP
                        result = {"lat": lat, "lon": lon, "source": "gps"}
                    else:
                        result = await get_location_from_ip(user_ip)
                elif fn_name == "get_weather":
                    result = await get_weather_data(args.get("lat", 0), args.get("lon", 0), city_hint=city_hint)
                
                contents.append(genai_types.Content(
                    role="tool",
                    parts=[genai_types.Part(function_response=genai_types.FunctionResponse(name=fn_name, response=result))]
                ))

            curr_response = client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=contents, config=config)
            
    except Exception as e:
        error_msg = str(e)
        if "503" in error_msg or "UNAVAILABLE" in error_msg:
            yield "Gemini is currently experiencing high demand (503). Please try switching to the **Groq** provider in the dropdown above for a faster response."
        else:
            yield f"Gemini Agent error: {error_msg}"

async def _run_groq_weather_agent(question: str, history: list = None, user_ip: str = None, lat: float = None, lon: float = None) -> AsyncGenerator[str, None]:
    """Groq/OpenAI-style agent implementation."""
    client = get_groq_client()
    if not client:
        yield "Groq API key is not configured."
        return

    
    full_prompt = question
    if lat is not None and lon is not None:
        full_prompt = f"[GPS CONTEXT: Lat {lat}, Lon {lon}] {question}"

    messages = [{"role": "system", "content": WEATHER_SYSTEM_PROMPT}]
    if history:
        # For weather, we only need the most recent context (last 4 messages) to save tokens/quota
        recent_history = history[-4:]
        for msg in recent_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": full_prompt})

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_location",
                "description": "Get the user's current latitude and longitude based on their IP.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather data for a specific latitude and longitude.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude"},
                        "lon": {"type": "number", "description": "Longitude"}
                    },
                    "required": ["lat", "lon"]
                }
            }
        }
    ]

    try:
        max_iterations = 5
        for _ in range(max_iterations):
            response = client.chat.completions.create(
                model=GROQ_AGENT_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
            messages.append(msg) # Add assistant's message (which might have tool_calls)

            if not msg.tool_calls:
                if msg.content:
                    clean_text = sanitize_output(msg.content)
                    if clean_text: yield clean_text
                break

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"[agent-groq] Calling tool: {fn_name}")
                
                # Pre-lookup city hint for better accuracy
                city_hint = None
                if user_ip:
                    ip_loc = await get_location_from_ip(user_ip)
                    city_hint = ip_loc.get("city")

                result = {}
                if fn_name == "get_current_location":
                    if lat is not None and lon is not None:
                        # Use provided GPS data instead of IP
                        result = {"lat": lat, "lon": lon, "source": "gps"}
                    else:
                        result = await get_location_from_ip(user_ip)
                elif fn_name == "get_weather":
                    result = await get_weather_data(args.get("lat", 0), args.get("lon", 0), city_hint=city_hint)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": json.dumps(result)
                })
            
            # Continue loop to send tool results back to LLM
            
    except Exception as e:
        yield f"Groq Agent error: {str(e)}"

async def _run_openai_weather_agent(question: str, history: list = None, user_ip: str = None, lat: float = None, lon: float = None) -> AsyncGenerator[str, None]:
    """OpenAI-specific agent implementation."""
    client = get_openai_client()
    if not client:
        yield "OpenAI API key is not configured."
        return

    
    full_prompt = question
    if lat is not None and lon is not None:
        full_prompt = f"[GPS CONTEXT: Lat {lat}, Lon {lon}] {question}"

    messages = [{"role": "system", "content": WEATHER_SYSTEM_PROMPT}]
    if history:
        # For weather, we only need the most recent context (last 4 messages) to save tokens/quota
        recent_history = history[-4:]
        for msg in recent_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": full_prompt})

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_location",
                "description": "Get the user's current latitude and longitude based on their IP.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather data for a specific latitude and longitude.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude"},
                        "lon": {"type": "number", "description": "Longitude"}
                    },
                    "required": ["lat", "lon"]
                }
            }
        }
    ]

    try:
        max_iterations = 5
        for _ in range(max_iterations):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
            messages.append(msg) # Add assistant's message (which might have tool_calls)

            if not msg.tool_calls:
                if msg.content:
                    clean_text = sanitize_output(msg.content)
                    if clean_text: yield clean_text
                break

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"[agent-openai] Calling tool: {fn_name}")
                
                # Pre-lookup city hint for better accuracy
                city_hint = None
                if user_ip:
                    ip_loc = await get_location_from_ip(user_ip)
                    city_hint = ip_loc.get("city")

                result = {}
                if fn_name == "get_current_location":
                    if lat is not None and lon is not None:
                        # Use provided GPS data instead of IP
                        result = {"lat": lat, "lon": lon, "source": "gps"}
                    else:
                        result = await get_location_from_ip(user_ip)
                elif fn_name == "get_weather":
                    result = await get_weather_data(args.get("lat", 0), args.get("lon", 0), city_hint=city_hint)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": json.dumps(result)
                })
            
            # Continue loop to send tool results back to LLM
            
    except Exception as e:
        yield f"OpenAI Agent error: {str(e)}"

async def _run_ollama_weather_agent(question: str, history: list = None, user_ip: str = None, lat: float = None, lon: float = None) -> AsyncGenerator[str, None]:
    """Ollama-specific agent implementation."""
    full_prompt = question
    if lat is not None and lon is not None:
        full_prompt = f"[GPS CONTEXT: Lat {lat}, Lon {lon}] {question}"

    messages = [{"role": "system", "content": WEATHER_SYSTEM_PROMPT}]
    if history:
        recent_history = history[-4:]
        for msg in recent_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": full_prompt})

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_location",
                "description": "Get the user's current latitude and longitude based on their IP.",
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather data for a specific latitude and longitude.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude"},
                        "lon": {"type": "number", "description": "Longitude"}
                    },
                    "required": ["lat", "lon"]
                }
            }
        }
    ]

    use_v1 = "/v1" in settings.OLLAMA_BASE_URL
    endpoint = f"{settings.OLLAMA_BASE_URL}/chat/completions" if use_v1 else f"{settings.OLLAMA_BASE_URL}/api/chat"
    model_name = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL else "llama3.2:3b"

    headers = {}
    auth = None
    if settings.OLLAMA_API_KEY:
        if ":" in settings.OLLAMA_API_KEY:
            user, pwd = settings.OLLAMA_API_KEY.split(":", 1)
            auth = (user, pwd)
        else:
            headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

    try:
        max_iterations = 5
        for _ in range(max_iterations):
            payload = {
                "model": model_name,
                "messages": messages,
                "tools": tools,
                "stream": False
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, auth=auth, timeout=180.0)
            
            if response.status_code != 200:
                try:
                    err_msg = response.json().get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text
                yield f"Ollama HTTP error {response.status_code}: {err_msg}"
                return

            data = response.json()
            if use_v1:
                msg = data.get("choices", [{}])[0].get("message", {})
            else:
                msg = data.get("message", {})

            # Append the assistant's message back to the thread
            messages.append(msg)

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                content = msg.get("content")
                if content:
                    clean_text = sanitize_output(content)
                    if clean_text: yield clean_text
                break

            for tool_call in tool_calls:
                fn_name = tool_call["function"]["name"]
                args_raw = tool_call["function"]["arguments"]
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {}
                else:
                    args = args_raw or {}

                print(f"[agent-ollama] Calling tool: {fn_name}")
                
                # Pre-lookup city hint
                city_hint = None
                if user_ip:
                    ip_loc = await get_location_from_ip(user_ip)
                    city_hint = ip_loc.get("city")

                result = {}
                if fn_name == "get_current_location":
                    if lat is not None and lon is not None:
                        result = {"lat": lat, "lon": lon, "source": "gps"}
                    else:
                        result = await get_location_from_ip(user_ip)
                elif fn_name == "get_weather":
                    result = await get_weather_data(args.get("lat", 0), args.get("lon", 0), city_hint=city_hint)
                
                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "content": json.dumps(result)
                })

    except Exception as e:
        yield f"Ollama Agent error: {str(e)}"
