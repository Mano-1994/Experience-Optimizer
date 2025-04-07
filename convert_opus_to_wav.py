from pydub import AudioSegment

# Convert OPUS to WAV
def convert_opus_to_wav(input_file, output_file):
    audio = AudioSegment.from_file(input_file, format="opus")
    audio.export(output_file, format="wav")
    print(f"Converted: {input_file} → {output_file}")

# Example usage
convert_opus_to_wav("C:\Users\mkalli\OneDrive - Voxai Solutions, Inc\Official\Intent-bot\audio\1f2f8dc7-9129-4559-92cf-00b548067f84.opus", "audio.wav")  # Replace with your file name

