import os
os.environ["OPENAI_API_KEY"] = "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"

import openai
import streamlit as st

# Set OpenAI API key securely (better to use secrets in production)
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_intents_and_utterances(transcript):
    system_prompt = """
You are an AI assistant designed to extract intents from conversation transcripts.
For each intent, generate a name and 3-5 example user utterances.

Return the output in JSON format like this:
{
  "intents": [
    {
      "name": "IntentName1",
      "utterances": [
        "example utterance 1",
        "example utterance 2"
      ]
    }
  ]
}
"""
    user_prompt = f"Transcript:\n{transcript}"

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )

    return response['choices'][0]['message']['content']

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Intent Extractor", layout="centered")
st.title("📄 Transcript Intent Extractor")

uploaded_file = st.file_uploader("Upload a transcript file (.txt)", type=["txt", "csv"])

if uploaded_file:
    transcript = uploaded_file.read().decode("utf-8")

    if st.button("Extract Intents"):
        with st.spinner("Analyzing transcript..."):
            try:
                output = extract_intents_and_utterances(transcript)
                st.success("Intents extracted successfully!")
                st.code(output, language="json")
            except Exception as e:
                st.error(f"Something went wrong: {e}")
