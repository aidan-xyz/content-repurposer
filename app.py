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
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    
    prompts = {
        'linkedin': """Convert this transcript into a LinkedIn post. Use this style:
- Start with a strong hook
- Short paragraphs (1-2 sentences each)
- Use bullet points where appropriate
- End with an engaging question
- Professional but authentic tone
- Keep it conversational

Transcript: {transcript}""",
        
        'twitter': """Convert this transcript into a Twitter thread. Use this style:
- Punchy and direct
- Each tweet should be under 280 characters
- Use line breaks for readability
- No hashtags unless absolutely necessary
- Start strong

Format as a thread with tweet numbers.

Transcript: {transcript}""",
        
        'blog': """Convert this transcript into a blog post. Use this style:
- Clear H2 headings for sections
- Medium-length paragraphs
- Expand on ideas from the transcript
- Professional but conversational
- Add context where needed
- No fluff

Transcript: {transcript}"""
    }
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": prompts[platform].format(transcript=transcript)
        }]
    )
    
    return message.content[0].text

@app.route('/')
@auth.login_required
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
@auth.login_required
def process_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload MP4, MOV, AVI, or MKV'}), 400
    
    try:
        # Save uploaded video
        filename = secure_filename(file.filename)
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(video_path)
        
        # Extract audio
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{filename}_audio.mp3")
        extract_audio(video_path, audio_path)
        
        # Transcribe
        transcript = transcribe_audio(audio_path)
        
        # Format for each platform
        linkedin_post = format_for_platform(transcript, 'linkedin')
        twitter_thread = format_for_platform(transcript, 'twitter')
        blog_post = format_for_platform(transcript, 'blog')
        
        # Clean up files
        os.remove(video_path)
        os.remove(audio_path)
        
        return jsonify({
            'transcript': transcript,
            'linkedin': linkedin_post,
            'twitter': twitter_thread,
            'blog': blog_post
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
