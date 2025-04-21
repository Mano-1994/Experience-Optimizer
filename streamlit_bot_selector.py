import os
import openai
import streamlit as st
import json
import tempfile
import subprocess
import yaml
import boto3
import time
from pydub import AudioSegment
import whisper
import sys
sys.modules["torch.classes"] = None

# --- API Keys and Constants ---
os.environ["OPENAI_API_KEY"] = "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"
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Genesys Archy Configuration ---
ARCHY_PATH = r"C:\\Users\\mkalli\\Archy\\archy-win\\archyBin\\archy-win-2.33.1.exe"
GENESYS_REGION = "mypurecloud.com"
GENESYS_DIVISION = "Home"
GENESYS_BOT_NAME = "Intent_bot_with_wav"

# --- Amazon Lex Configuration ---
LEX_REGION = "us-west-2"
LEX_BOT_NAME = "Experience_optimizer"
LEX_LOCALE_ID = "en_US"
LEX_BOT_ROLE_ARN = "arn:aws:iam::661256828619:role/Experience_Optimizer_POC"

# ---------- Whisper STT ----------
def transcribe_audio(audio_path, is_opus=False):
    if is_opus:
        wav_path = audio_path.replace(".opus", ".wav")
        audio = AudioSegment.from_file(audio_path, format="opus")
        audio.export(wav_path, format="wav")
        audio_path = wav_path
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]

# ---------- Intent Extraction ----------
def extract_intents_and_utterances(transcript):
    system_prompt = """
You are an AI assistant designed to extract structured intents from a transcript.
For each intent, generate:
- A descriptive intent name
- 3-5 example user utterances
- A list of slots (i.e., variable fields) that are required to fulfill that intent

Return the output in JSON format like this:
{
  "intents": [
    {
      "name": "IntentName1",
      "utterances": ["example 1", "example 2"],
      "slots": ["Slot1", "Slot2"]
    }
  ]
}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript:\n{transcript}"}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    return json.loads(response['choices'][0]['message']['content'])

# ---------- Genesys YAML ----------
def convert_to_yaml(bot_name, division, intents_json):
    return {
        "botFlow": {
            "name": bot_name,
            "division": division,
            "defaultLanguage": "en-us",
            "startUpRef": "/botFlow/bots/bot[Default Bot_1]",
            "bots": [{
                "bot": {
                    "name": "Default Bot",
                    "refId": "Default Bot_1",
                    "actions": [{
                        "askForIntent": {
                            "name": "Ask for Intent",
                            "question": {"exp": "MakeCommunication(\"Please tell me how I can assist you.\")"},
                            "inputMode": "DtmfOnly",
                            "outputs": {
                                "intents": [
                                    {"intent": {
                                        "name": intent["name"],
                                        "enabled": True,
                                        "slots": [{"name": slot} for slot in intent.get("slots", [])]
                                    }} for intent in intents_json["intents"]
                                ]
                            }
                        }
                    }, {"exitBotFlow": {"name": "Exit"}}]
                }}],
            "settingsBotFlow": {
                "intentSettings": [
                    {"intent": {"name": intent["name"], "confirmation": {"exp": f'MakeCommunication("Is this about {intent["name"]}?")'}}} for intent in intents_json["intents"]
                ]
            },
            "settingsNaturalLanguageUnderstanding": {
                "nluDomainVersion": {
                    "language": "en-us",
                    "intents": [
                        {
                            "name": intent["name"],
                            "utterances": [
                                {"segments": [{"text": utt}], "id": f"auto-{i}-{j}"} for j, utt in enumerate(intent["utterances"])
                            ],
                            "entityNameReferences": [],
                            "id": f"auto-id-{i}"
                        } for i, intent in enumerate(intents_json["intents"])
                    ]
                }
            }
        }
    }

def publish_to_genesys(yaml_obj):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
        yaml.dump(yaml_obj, tmp_file)
        tmp_file_path = tmp_file.name

    def run_archy(cmd):
        return subprocess.run(cmd, capture_output=True, text=True).returncode == 0

    return run_archy([ARCHY_PATH, "create", "--file", tmp_file_path, "--location", GENESYS_REGION]) and \
           run_archy([ARCHY_PATH, "publish", "--file", tmp_file_path, "--location", GENESYS_REGION])

# ---------- Amazon Lex ----------
lex_client = boto3.client("lexv2-models", region_name=LEX_REGION)

def wait_for_lex_version_available(bot_id, version):
    while True:
        versions = lex_client.list_bot_versions(botId=bot_id)["botVersionSummaries"]
        status = next((v["botStatus"] for v in versions if v["botVersion"] == version), None)
        if status == "Available": break
        time.sleep(5)

def create_and_publish_lex_bot(intents_json):
    response = lex_client.create_bot(
        botName=LEX_BOT_NAME,
        description="Lex bot from UI",
        roleArn=LEX_BOT_ROLE_ARN,
        dataPrivacy={"childDirected": False},
        idleSessionTTLInSeconds=300
    )
    bot_id = response["botId"]
    while lex_client.describe_bot(botId=bot_id)["botStatus"] != "Available": time.sleep(3)

    lex_client.create_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=LEX_LOCALE_ID, nluIntentConfidenceThreshold=0.4)
    while lex_client.describe_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=LEX_LOCALE_ID)["botLocaleStatus"] != "NotBuilt": time.sleep(3)

    for intent in intents_json["intents"]:
        lex_client.create_intent(
            botId=bot_id,
            botVersion="DRAFT",
            localeId=LEX_LOCALE_ID,
            intentName=intent["name"],
            sampleUtterances=[{"utterance": utt} for utt in intent["utterances"]]
        )

    lex_client.build_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=LEX_LOCALE_ID)
    while lex_client.describe_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=LEX_LOCALE_ID)["botLocaleStatus"] != "Built": time.sleep(5)

    version = lex_client.create_bot_version(botId=bot_id, botVersionLocaleSpecification={LEX_LOCALE_ID: {"sourceBotVersion": "DRAFT"}})["botVersion"]
    wait_for_lex_version_available(bot_id, version)

    lex_client.create_bot_alias(
        botAliasName="prod",
        botId=bot_id,
        botVersion=version,
        botAliasLocaleSettings={LEX_LOCALE_ID: {"enabled": True}}
    )
    return True

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Bot Generator", layout="centered")
st.title("🎙️ Audio/Text → Intents → Bot")

bot_type = st.radio("Choose Bot Platform:", ["Genesys", "Amazon Lex"])
input_type = st.radio("Input Type:", ["Text File", "Audio File"])
transcript = None

if input_type == "Text File":
    uploaded_file = st.file_uploader("Upload transcript file", type=["txt", "csv"])
    if uploaded_file:
        transcript = uploaded_file.read().decode("utf-8")
else:
    uploaded_audio = st.file_uploader("Upload audio file", type=["wav", "opus"])
    if uploaded_audio:
        ext = uploaded_audio.name.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            tmp.write(uploaded_audio.read())
            transcript = transcribe_audio(tmp.name, is_opus=(ext == "opus"))

if transcript and st.button("Extract & Publish Bot"):
    with st.spinner("Extracting intents & publishing bot..."):
        try:
            intents_json = extract_intents_and_utterances(transcript)
            if bot_type == "Genesys":
                success = publish_to_genesys(convert_to_yaml(GENESYS_BOT_NAME, GENESYS_DIVISION, intents_json))
            else:
                success = create_and_publish_lex_bot(intents_json)

            if success:
                st.success(f"✅ {bot_type} Bot published successfully!")
            else:
                st.error(f"❌ Failed to publish to {bot_type}.")

        except Exception as e:
            st.error(f"❌ Error: {e}")