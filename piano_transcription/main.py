from flask import Flask, Response, request, send_file
from flask_cors import CORS
from piano_transcription_inference import PianoTranscription, sample_rate, load_audio
from music21 import converter
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'temp'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

transcriptor = PianoTranscription(device='cpu')    # 'cuda' | 'cpu'

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return 'No file uploaded', 400

    file = request.files['audio']
    if file.filename == '':
        return 'No file selected', 400

    input_path = os.path.join(UPLOAD_FOLDER, 'input.wav')
    output_path = os.path.join(UPLOAD_FOLDER, 'output.mid')
    file.save(input_path)

    try:
        (audio, _) = load_audio(input_path, sr=sample_rate, mono=True)

        transcribed_dict = transcriptor.transcribe(audio, output_path)

        if not os.path.exists(output_path):
            return "Error: MIDI file not created", 500
        
        with open(output_path, "rb") as f:
            midi_data = f.read()

        os.remove(input_path)
        os.remove(output_path)
        return Response(midi_data, mimetype="audio/midi")

    except Exception as e:
        return f'Error during transcription: {str(e)}', 500

if __name__ == '__main__':
    app.run(port=8010, debug=True)