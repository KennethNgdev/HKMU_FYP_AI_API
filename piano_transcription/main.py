from flask import Flask, Response, request, send_file, jsonify
from flask_cors import CORS
from piano_transcription_inference import PianoTranscription, sample_rate, load_audio
from music21 import converter
import os
import logging

app = Flask(__name__)
CORS(app)


UPLOAD_FOLDER = 'temp'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

transcriptor = PianoTranscription(checkpoint_path="model_weight.pth", device='cpu')    # 'cuda' | 'cpu'

@app.route("/test")
def test():
    return '''
    <!doctype html>
    <title>Upload WAV File</title>
    <h1>Upload a WAV file for transcription</h1>
    <form method="POST" action="/transcribe" enctype="multipart/form-data">
      <input type="file" name="audio" accept=".wav">
      <input type="submit" value="Upload">
    </form>
    '''

@app.route('/transcribe', methods=['POST'])
def transcribe():
    print('Transcription request received', flush=True)
    if 'audio' not in request.files:
        print('No file uploaded', flush=True)
        return 'No file uploaded', 400

    file = request.files['audio']
    if file.filename == '':
        print('No file selected', flush=True)
        return 'No file selected', 400

    input_path = os.path.join(UPLOAD_FOLDER, 'input.wav')
    output_path = os.path.join(UPLOAD_FOLDER, 'output.mid')
    file.save(input_path)
    print(f'File saved to {input_path}', flush=True)

    try:
        (audio, _) = load_audio(input_path, sr=sample_rate, mono=True)
        print('Audio loaded', flush=True)
        print('Audio loaded', flush=True)

        print('Transcribing...', flush=True)
        transcribed_dict = transcriptor.transcribe(audio, output_path)
        print('Transcription completed', flush=True)

        if not os.path.exists(output_path):
            print('Error: MIDI file not created', flush=True)
            return "Error: MIDI file not created", 500
        
        with open(output_path, "rb") as f:
            midi_data = f.read()

        os.remove(input_path)
        os.remove(output_path)
        return Response(midi_data, mimetype="audio/midi")

    except Exception as e:
        print(f'Error during transcription: {str(e)}', flush=True)
        return f'Error during transcription: {str(e)}', 500

if __name__ == '__main__':
    app.run(host= "0.0.0.0", port=8010, debug=True)