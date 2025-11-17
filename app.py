import os
from flask import Flask, render_template, request, jsonify
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash
import subprocess
import anthropic
import openai
from werkzeug.utils import secure_filename

app = Flask(__name__)
auth = HTTPBasicAuth()
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'mov', 'avi', 'mkv'}

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Authentication
@auth.verify_password
def verify_password(username, password):
    expected_username = os.environ.get('AUTH_USERNAME')
    expected_password = os.environ.get('AUTH_PASSWORD')
    
    if not expected_username or not expected_password:
        # If no auth is configured, allow access
        return True
    
    if username == expected_username and password == expected_password:
        return username
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_audio(video_path, audio_path):
    """Extract audio from video using FFmpeg"""
    # Try to find ffmpeg in common locations
    ffmpeg_cmd = 'ffmpeg'
    possible_paths = [
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        'ffmpeg'
    ]
    
    for path in possible_paths:
        try:
            subprocess.run([path, '-version'], capture_output=True, check=True)
            ffmpeg_cmd = path
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    command = [
        ffmpeg_cmd, '-i', video_path,
        '-vn', '-acodec', 'libmp3lame',
        '-q:a', '2', audio_path, '-y'
    ]
    subprocess.run(command, check=True, capture_output=True)

def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper API"""
    client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    
    with open(audio_path, 'rb') as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text

def format_for_platform(transcript, platform):
    """Use Claude to format transcript for specific platform"""
    print(f"Creating Anthropic client for {platform}...")
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    prompts = {
        'linkedin': """Convert this transcript into a LinkedIn post.

Rules:
- NO markdown formatting (no **, no #, no formatting symbols)
- Stay very close to the original transcript's content and ideas
- Start with a single strong hook line
- Use short paragraphs (1-2 sentences each)
- Use simple dashes for bullet points if needed
- Professional but authentic tone
- Keep it conversational and direct
- DO NOT end with a question or CTA - just end naturally

Transcript: {transcript}""",
        
        'twitter': """Convert this transcript into a single Twitter post (not a thread - Twitter allows longer posts now).

Rules:
- NO markdown formatting (no **, no #, no formatting symbols)
- Stay very close to the original transcript's content and ideas
- Punchy and direct
- Use line breaks for readability
- Use simple dashes for bullet points if needed
- Keep the same vibe as the transcript
- Start strong with a hook

Transcript: {transcript}""",
        
        'blog': """Convert this transcript into a blog post in a Substack style.

Rules:
- NO markdown formatting (no **, no #, no formatting symbols)
- Stay very close to the original transcript's content and ideas
- Use plain text section headings (simple, punchy)
- Organize into clear sections with SHORT paragraphs (2-4 sentences)
- Use single sentence paragraphs SPARINGLY for emphasis - not for everything
- Professional but conversational tone matching the transcript
- Be direct and to the point - no fluff
- Can end with a thought-provoking question
- Write like you're talking to a friend who's smart

Example structure:
Section Heading
Regular paragraph with 2-4 sentences explaining a point.

Maybe a single sentence for emphasis.

Another paragraph continuing the idea.

Next Section
And so on.

Transcript: {transcript}"""
    }
    
    print(f"Sending request to Claude for {platform}...")
    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompts[platform].format(transcript=transcript)
            }],
            timeout=120.0
        )
        print(f"Received response from Claude for {platform}")
        return message.content[0].text
    except Exception as e:
        print(f"ERROR in format_for_platform({platform}): {type(e).__name__}: {str(e)}")
        raise

@app.route('/')
@auth.login_required
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
@auth.login_required
def process_video():
    if 'video' not in request.files:
        print("ERROR: No video file in request")
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    
    if file.filename == '':
        print("ERROR: Empty filename")
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        print(f"ERROR: Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type. Please upload MP4, MOV, AVI, or MKV'}), 400
    
    try:
        # Save uploaded video
        filename = secure_filename(file.filename)
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"Saving video to: {video_path}")
        file.save(video_path)
        
        # Extract audio
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{filename}_audio.mp3")
        print(f"Extracting audio to: {audio_path}")
        extract_audio(video_path, audio_path)
        
        # Transcribe
        print("Starting transcription...")
        transcript = transcribe_audio(audio_path)
        print(f"Transcription complete: {len(transcript)} characters")
        
        # Clean up files immediately
        print("Cleaning up temporary files...")
        os.remove(video_path)
        os.remove(audio_path)
        
        # Return transcript immediately
        print("SUCCESS: Transcription complete, returning to client")
        return jsonify({
            'transcript': transcript
        })
    
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/format', methods=['POST'])
@auth.login_required
def format_content():
    """Format transcript for specific platforms"""
    data = request.get_json()
    
    if not data or 'transcript' not in data:
        return jsonify({'error': 'No transcript provided'}), 400
    
    transcript = data['transcript']
    platforms = data.get('platforms', ['linkedin', 'twitter', 'blog'])
    
    try:
        results = {}
        for platform in platforms:
            print(f"Formatting for {platform}...")
            results[platform] = format_for_platform(transcript, platform)
            print(f"Completed {platform}")
        
        return jsonify(results)
    
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Flask app...")
    print(f"ANTHROPIC_API_KEY set: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
    print(f"OPENAI_API_KEY set: {bool(os.environ.get('OPENAI_API_KEY'))}")
    print(f"AUTH_USERNAME set: {bool(os.environ.get('AUTH_USERNAME'))}")
    print(f"AUTH_PASSWORD set: {bool(os.environ.get('AUTH_PASSWORD'))}")
    app.run(debug=True, host='0.0.0.0', port=5000)
