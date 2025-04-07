import os
os.environ["OPENAI_API_KEY"] = "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"

import openai
import os

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
        "example utterance 2",
        ...
      ]
    },
    ...
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

# Sample usage
if __name__ == "__main__":
    transcript_text = """
   Yeah, actually that would be perfect. I won’t be home during the day, so can we schedule mail delivery for after 6 PM or maybe sometime during the weekend?
    """
    
    result = extract_intents_and_utterances(transcript_text)
    print(result)
