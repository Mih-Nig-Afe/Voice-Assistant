# AI-Powered Voice Assistant - Miehab

Miehab is an interactive AI-driven voice assistant that combines speech recognition, text-to-speech, and AI-based natural language processing to assist users with hands-free interaction. It provides dynamic responses, weather updates, Wikipedia summaries, and more.

---

## Features

- **Voice Interaction**: Listens and responds to user queries using speech.
- **Text-to-Speech**: Provides vocal responses for hands-free convenience.
- **AI-Powered Responses**: Generates intelligent replies using the GPT-Neo model.
- **Weather Updates**: Fetches real-time weather data for any city using the OpenWeather API.
- **Wikipedia Integration**: Retrieves and reads summaries of requested topics.
- **Audio Feedback**: Plays customizable beeps to indicate listening status.

---

## Getting Started

Follow these steps to set up and use Miehab:

### Prerequisites

1. Install Python (version 3.7 or above).
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Obtain an API key from [OpenWeather](https://openweathermap.org/) for weather updates.

---

### Usage

1. Clone the repository:
   ```bash
   git clone <repository_url>
   ```

2. Navigate to the project directory:
   ```bash
   cd <project_directory>
   ```

3. Add your OpenWeather API key to the script.

4. Run the script:
   ```bash
   python main.py
   ```

5. Speak commands like:
   - "What's the weather in [city]?"
   - "Tell me about [topic]."
   - "Goodbye" (to exit).

---

## Example Commands

- **Weather**: "What's the weather in Addis Ababa?"
- **Wikipedia**: "Tell me about artificial intelligence."
- **Casual Talk**: "How are you today?"

---

## File Structure

- `main.py`: The main script for running Miehab.
- `requirements.txt`: List of dependencies.
- `sounds/`: Folder containing beep sound files.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Contribution

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add some feature"
   ```
4. Push to the branch:
   ```bash
   git push origin feature/your-feature-name
   ```
5. Open a pull request.

---

## Acknowledgements

- Built with Python and open-source libraries like `speech_recognition`, `pyttsx3`, and `transformers`.
- Weather data powered by OpenWeather.
- Summaries provided by Wikipedia.

---

### Note
Ensure your microphone and speakers are properly configured for the best experience. Sensitive information like API keys should be stored securely (e.g., in environment variables).
