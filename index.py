import io
import os
import sys
import logging
import pandas as pd

# Ensure local api folder and root are available in module search path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from api.analysis import analyze_genetic_bottleneck, AnalysisValidationError
except ImportError:
    from analysis import analyze_genetic_bottleneck, AnalysisValidationError

from flask import Flask, request, jsonify

# Configure safe logging (no sensitive individual IDs or genotype calls logged)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ecogen_diagnostics")

app = Flask(__name__)

# Enforce 4 MB upload limit (safe below Vercel's 4.5 MB request payload limit)
MAX_UPLOAD_SIZE = 4 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE

@app.errorhandler(413)
def request_entity_too_large(error):
    logger.warning("Upload rejected: payload exceeds size limit.")
    return jsonify({
        "error": "File size exceeds the 4 MB limit allowed for analysis."
    }), 413

@app.errorhandler(400)
def bad_request(error):
    msg = getattr(error, 'description', 'Bad Request')
    return jsonify({"error": msg}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "The requested API endpoint was not found."}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "HTTP method not allowed on this endpoint."}), 405

@app.errorhandler(500)
def internal_server_error(error):
    logger.exception("Internal server error occurred during request processing")
    return jsonify({
        "error": "An internal server error occurred while processing the analysis."
    }), 500

@app.route('/api/health', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "ok": True,
        "service": "EcoGen Diagnostics"
    }), 200

@app.route('/api/upload', methods=['POST'])
@app.route('/upload', methods=['POST'])
def upload():
    # 1. Validate file presence in multipart request
    if 'file' not in request.files:
        logger.warning("Upload rejected: 'file' field missing from multipart request.")
        return jsonify({
            "error": "No file uploaded. Please upload a CSV file with field name 'file'."
        }), 400

    file_obj = request.files['file']
    if not file_obj or not file_obj.filename:
        logger.warning("Upload rejected: empty file selection.")
        return jsonify({
            "error": "No file selected."
        }), 400

    filename = file_obj.filename.strip()
    if not filename.lower().endswith('.csv'):
        logger.warning("Upload rejected: invalid file extension for filename '%s'.", filename)
        return jsonify({
            "error": "Invalid file type. Only .csv files are supported."
        }), 400

    # 2. Read file in memory (strictly no disk persistence)
    try:
        content_bytes = file_obj.read()
    except Exception as e:
        logger.exception("Failed to read uploaded file stream")
        return jsonify({
            "error": "Failed to read uploaded file."
        }), 400

    if len(content_bytes) == 0:
        logger.warning("Upload rejected: file '%s' is empty (0 bytes).", filename)
        return jsonify({
            "error": "Uploaded CSV file is empty."
        }), 400

    if len(content_bytes) > MAX_UPLOAD_SIZE:
        logger.warning("Upload rejected: file '%s' exceeds size limit (%d bytes).", filename, len(content_bytes))
        return jsonify({
            "error": "File size exceeds the 4 MB limit."
        }), 413

    # 3. Parse CSV safely with pandas in memory (treat all values as string/categorical)
    try:
        df = pd.read_csv(
            io.BytesIO(content_bytes),
            dtype=str,
            skipinitialspace=True
        )
    except Exception as e:
        logger.warning("Malformed CSV parsing failed for '%s': %s", filename, type(e).__name__)
        return jsonify({
            "error": "Malformed CSV file: unable to parse data structure."
        }), 400

    if df.empty or len(df) == 0:
        logger.warning("Upload rejected: file '%s' has 0 data rows.", filename)
        return jsonify({
            "error": "CSV contains no data rows (empty or header-only)."
        }), 400

    if len(df.columns) == 0:
        logger.warning("Upload rejected: file '%s' has no columns.", filename)
        return jsonify({
            "error": "CSV contains no columns."
        }), 400

    # 4. Perform analysis calculations & validations
    try:
        results = analyze_genetic_bottleneck(df)
        logger.info(
            "Successfully analyzed file '%s': %d samples, %d loci, status %s.",
            filename,
            results['summary']['sample_count'],
            results['summary']['locus_count'],
            results['status']
        )
        return jsonify(results), 200
    except AnalysisValidationError as ve:
        logger.warning("Validation error analyzing '%s': %s", filename, str(ve))
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Unexpected exception analyzing '%s'", filename)
        return jsonify({
            "error": "An unexpected error occurred while analyzing the dataset."
        }), 500
