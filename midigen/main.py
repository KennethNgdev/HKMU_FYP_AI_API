from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import math
from werkzeug.utils import secure_filename
import os

from util import  (
    get_midi_key, get_midi_info, generate_chord_measures,
    create_chord_midi_from_measures, compute_average_velocity,
    apply_volume_to_midi, combine_midis
)

app = Flask(__name__)
CORS(app)

app.debug = True

HOST = "0.0.0.0"
PORT = 8020

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mid', 'midi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/test')
def index():
    """Serve a simple HTML form for testing."""
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>MIDI Combiner</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }
                .form-container {
                    max-width: 400px;
                    margin: 0 auto;
                    padding: 20px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    background-color: #f9f9f9;
                }
                .form-container h2 {
                    text-align: center;
                }
                .form-container label {
                    display: block;
                    margin: 10px 0 5px;
                }
                .form-container input[type="text"],
                .form-container input[type="file"] {
                    width: 100%;
                    padding: 8px;
                    margin-bottom: 10px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
                .form-container input[type="submit"] {
                    width: 100%;
                    padding: 10px;
                    background-color: #28a745;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                .form-container input[type="submit"]:hover {
                    background-color: #218838;
                }
            </style>
        </head>
        <body>
            <div class="form-container">
                <h2>MIDI Combiner</h2>
                <form action="/combine_midi" method="post" enctype="multipart/form-data">
                    <label for="file">Upload MIDI File:</label>
                    <input type="file" name="file" id="file" accept=".mid,.midi" required>

                    <label for="key">Key (e.g., C, D, E):</label>
                    <input type="text" name="key" id="key" placeholder="C" default="C">

                    <label for="mode">Mode (e.g., Major, Minor):</label>
                    <input type="text" name="mode" id="mode" placeholder="Major" default="Major">

                    <label for="progression">Chord Progression (e.g., 2,5,1,6):</label>
                    <input type="text" name="progression" id="progression" placeholder="2,5,1,6" default="2,5,1,6">

                    <label for="time_sig">Time Signature (e.g., 4,4):</label>
                    <input type="text" name="time_sig" id="time_sig" placeholder="4,4" default="4,4">

                    <label for="tempo">Tempo (e.g., 90):</label>
                    <input type="text" name="tempo" id="tempo" placeholder="90" default="90"> >

                    <input type="submit" value="Combine MIDI">
                </form>
            </div>
        </body>
        </html>
    ''')

@app.route('/combine_midi', methods=['POST'])
def combine_midi():
    # Handle file upload
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only MIDI files are allowed."}), 400

    # Save the uploaded file
    filename = secure_filename(file.filename)
    input_midi_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_midi_file)

    # Get user inputs or use defaults
    key = request.form.get('key', 'C')  # Default key is 'C'
    mode_str = request.form.get('mode', 'Major')  # Default mode is 'Major'
    progression = request.form.get('progression', '2,5,1,6')  # Default progression is '2,5,1,6'
    time_sig = request.form.get('time_sig', '4,4')  # Default time signature is '4,4'
    tempo = request.form.get('tempo', '90')  # Default tempo is 90

    # Convert inputs to appropriate types
    try:
        progression = list(map(int, progression.split(',')))
        time_sig = tuple(map(int, time_sig.split(',')))
        tempo = int(tempo)
    except ValueError:
        return jsonify({"error": "Invalid input format for progression, time signature, or tempo."}), 400

    # Process the MIDI file
    try:
        detected_key = get_midi_key(input_midi_file, default_key=key)
        mode_str = mode_str
        progression = progression
        time_sig = time_sig
        default_tempo = tempo

        # Get MIDI info
        try:
            tempo, duration = get_midi_info(input_midi_file)
        except Exception as e:
            print(e)
            print("Using default BPM and duration")
            tempo = default_tempo
            duration = 60

        # Calculate measures
        measure_length = (time_sig[0] * 60) / tempo
        total_measures_needed = math.ceil(duration / measure_length)
        repeats = math.ceil(total_measures_needed / len(progression))

        # Generate chord measures
        measures = generate_chord_measures(detected_key, mode_str, progression, time_sig, tempo, repeats)

        # Create chord MIDI object
        chord_midi_object = create_chord_midi_from_measures(measures, tempo)

        # Adjust volume
        desired_volume = compute_average_velocity(input_midi_file)
        apply_volume_to_midi(chord_midi_object, desired_volume)

        # Combine MIDI files
        output_file = os.path.join(app.config['UPLOAD_FOLDER'], 'combined_output.mid')
        combine_midis(input_midi_file, chord_midi_object, output_file)

        # Delete the input MIDI file
        os.remove(input_midi_file)

        # Return the combined MIDI file as a response
        return send_file(output_file, as_attachment=True, download_name='combined_output.mid')

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    host = os.getenv('HOST', HOST)
    port = os.getenv('PORT', PORT)
    app.run(host= host, port = port)