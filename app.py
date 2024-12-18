'''
Author: Mih-Nig-Afe mtabdevt@gmail.com
Date: 2024-12-05 20:59:45
LastEditors: Mihretab Nigatu mtabdevt@gmail.com
LastEditTime: 2024-12-18 12:44:41
FilePath: \Voice Assistant\app.py
Description:
This project is an AI-based voice assistant named "Miehab" that interacts with users through speech. 

Features:
- Speech recognition using `speech_recognition`.
- Text-to-speech responses with `pyttsx3`.
- AI-powered replies via GPT-Neo from `transformers`.
- Weather updates using OpenWeather API.
- Wikipedia integration for topic summaries.

How to Use:
1. Install the required libraries.
2. Add your OpenWeather API key.
3. Run the script to start interacting with Miehab.

Note: Ensure your microphone and speakers are configured correctly.

'''

import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from transformers.utils.logging import set_verbosity_error
import requests
import wikipedia
import threading
import os
from playsound import playsound  # Updated library for sound playback

# Suppress warnings from transformers
set_verbosity_error()

# Initialize text generation model
try:
    generator = pipeline('text-generation', model='EleutherAI/gpt-neo-125M')  # Lightweight model
except Exception as e:
    print(f"AI generation is currently unavailable: {e}")
    generator = None

# Initialize text-to-speech engine
engine = pyttsx3.init()
engine.setProperty("rate", 160)  # Adjust speech rate
voices = engine.getProperty("voices")
# Select  male voice
male_voice = next((voice for voice in voices if "male" in voice.name.lower()), voices[0])
engine.setProperty("voice", male_voice.id)

# Lock to manage the speech engine concurrency
engine_lock = threading.Lock()

# Define paths to the beep sound files
START_BEEP_PATH = r'c:\Users\TS PDA\Documents\Projects\Python\Voice Assistant\sounds1\point-smooth-beep-230573.wav'
STOP_BEEP_PATH = r'c:\Users\TS PDA\Documents\Projects\Python\Voice Assistant\sounds1\beep-6-96243.wav'

# Function to play beep sound
def play_beep(start=True):
    beep_file = START_BEEP_PATH if start else STOP_BEEP_PATH
    if os.path.exists(beep_file):
        try:
            playsound(beep_file)  # Use playsound for sound playback
        except Exception as e:
            print(f"Error while playing {beep_file}: {e}")

# Function to convert text to speech
def speak(text):
    with engine_lock:  # Ensure only one thread accesses the engine at a time
        engine.say(text)
        engine.runAndWait()

# Function to recognize speech
def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening...")
        play_beep(start=True)  # Beep when starting to listen
        try:
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=12)
            play_beep(start=False)  # Beep when ending listening
            print("Processing...")
            query = recognizer.recognize_google(audio)
            print(f"You said: {query}")
            return query
        except sr.UnknownValueError:
            play_beep(start=False)  # Beep on failed listen
            print("Sorry, I didn't catch that. Could you repeat?")
            speak("Sorry, I didn't catch that. Could you repeat?")
            return ""
        except sr.RequestError:
            play_beep(start=False)  # Beep on failed listen
            print("There seems to be an internet issue. Please check your connection.")
            speak("There seems to be an internet issue. Please check your connection.")
            return ""
        except Exception as e:
            play_beep(start=False)  # Beep on failed listen
            print(f"Error: {e}")
            speak("Something went wrong. Could you try again?")
            return ""

# Function to generate AI response
def generate_ai_response(prompt):
    if generator:
        try:
            response = generator(prompt, max_length=100, num_return_sequences=1)
            return response[0]["generated_text"].strip()
        except Exception as e:
            print(f"Error generating AI response: {e}")
            return "I couldn't think of a response. Let me try again later."
    else:
        return "AI generation isn't available at the moment."

# Function to get weather information
def get_weather(city, api_key):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    try:
        response = requests.get(url)
        data = response.json()
        if data["cod"] != 200:
            return f"Error: {data['message']}"
        weather = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        return f"{city.capitalize()} weather: {weather}, {temp}°C, feels like {feels_like}°C."
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return "I couldn't fetch the weather details. Please try later."

# Function to fetch 3-7 sentences from Wikipedia
def get_wikipedia_summary(query):
    try:
        wikipedia.set_lang("en")  # Set language to English
        summary = wikipedia.summary(query, sentences=7)  # Fetch up to 7 sentences
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options[:3]  # Show top 3 options for clarification
        return f"Your query is too broad. Did you mean: {', '.join(options)}?"
    except wikipedia.exceptions.PageError:
        return "I couldn't find any information on that topic. Please try rephrasing."
    except Exception as e:
        print(f"Error accessing Wikipedia: {e}")
        return "I encountered an issue accessing Wikipedia. Please try again later."

# Main function
def ai_talking_friend(api_key):
    print("Hi, I'm Miehab, your personal voice assistant. How can I help you today?")
    speak("Hi, I'm Miehab, your personal voice assistant. How can I help you today?")

    while True:
        user_query = listen()

        if not user_query:
            continue

        if "bye" in user_query.lower():
            print("Goodbye! Talk to you soon!")
            speak("Goodbye! Talk to you soon!")
            break

        if "weather" in user_query.lower():
            print("Which city should I check?")
            speak("Which city should I check?")
            city = listen()
            if city:
                weather_info = get_weather(city, api_key)
                print(weather_info)
                speak(weather_info)
            else:
                print("I couldn't understand the city name. Please try again.")
                speak("I couldn't understand the city name. Please try again.")

        elif "Wikipedia" in user_query.lower() or "tell me about" in user_query.lower():
            topic = user_query.replace("Wikipedia", "").replace("tell me about", "").strip()
            if topic:
                print(f"Searching Wikipedia for {topic}...")
                speak(f"Searching Wikipedia for {topic}...")
                summary = get_wikipedia_summary(topic)
                print(summary)
                speak(summary)
            else:
                print("Please specify a topic for me to search.")
                speak("Please specify a topic for me to search.")

        else:
            print("Thinking...")
            speak("Thinking...")
            response = generate_ai_response(user_query)
            print(response)
            speak(response)

        # Prompt user for further assistance
        additional_help_message = "Do you need help with anything else?"
        print(additional_help_message)
        speak(additional_help_message)

# OpenWeather API key
API_KEY = "0e66cfb4c038c19707aadd74d4c14ac7"

if __name__ == "__main__":
    ai_talking_friend(API_KEY)