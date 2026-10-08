# EcoGen Diagnostics

**EcoGen Diagnostics** is a high-precision, responsive population genetics screening application designed for conservation biologists, molecular ecologists, and geneticists. It analyzes diploid microsatellite and SNP marker datasets to assess population heterozygosity, inbreeding coefficients ($F_{is}$), and preliminary bottleneck screening indicators.

The application is engineered to deploy seamlessly as a serverless application on **Vercel** using a Python Flask backend (`api/index.py`) and an accessible, responsive dark scientific frontend (`public/`).

---

## 1. Root Cause Diagnosis & Resolution

### The Issue
Previous deployments showed the error message:
> *“The analysis service returned an unreadable response. Please try again.”*

### Why This Happened
1. **Static Fallback Shadowing the API Route**: In standard Vercel SPA setups, a catch-all rewrite rule (`/(.*) -> /index.html`) or lack of an explicit API rewrite causes HTTP requests to `/api/upload` to be intercepted by the static file server instead of reaching the Python runtime. The server returns a `200 OK` or `404 Not Found` response with `Content-Type: text/html` containing HTML source code (`<!DOCTYPE html>...`).
2. **Blind JSON Parsing in Frontend**: When the frontend client executed `await response.json()` without checking `response.ok` or `response.headers.get("content-type")`, the browser threw a JavaScript `SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON`. The error-handling code caught this exception and showed the generic "unreadable response" message.
3. **Function Invocation Failures**: If dependencies were misconfigured or the Python entrypoint failed to initialize (e.g. calling blocking `app.run()`), Vercel returned an HTML `500 Internal Server Error` page, triggering the same parse failure.

### The Fix
1. **Vercel Routing Configuration (`vercel.json`)**: Configured strict priority routing that maps `/api/(.*)` directly to `/api/index.py`. All static assets are served from `public/`, ensuring `/api/upload` can never fall through to HTML.
2. **Robust Frontend Response Inspection (`public/app.js`)**:
   - The client inspects `response.status` and `Content-Type` before attempting JSON deserialization.
   - If a non-JSON response is received (e.g. HTML 404 or 500), the UI displays the exact HTTP status code, the response content type, a truncated response snippet, and recommended troubleshooting steps.
   - If the API returns a structured JSON error (`{"error": "..."}`), the application displays the server's specific message rather than a generic parsing error.
   - All server-provided text is inserted safely via `textContent` (no `innerHTML`), eliminating XSS risks.
3. **Vercel-Optimized Flask Entrypoint (`api/index.py`)**:
   - Clean WSGI `app` export without blocking `app.run()`.
   - Explicit `GET /api/health` and `POST /api/upload` route declarations.
   - Global JSON error handlers for HTTP 400, 404, 405, 413, and 500.

---

## 2. Dataset Specifications & CSV Validation

EcoGen Diagnostics expects standard tabular CSV files containing one individual per row and diploid locus columns.

### Column Naming Convention
- **Paired Locus Columns**: Must match `Locus<number>_A1` and `Locus<number>_A2` (e.g., `Locus1_A1` and `Locus1_A2`, `Locus2_A1` and `Locus2_A2`).
- **Metadata Columns**: Columns such as `Individual_ID`, `Pop_ID`, or `Sampling_Year` are automatically identified and ignored during genotype calculations.

### Validation Rules
1. **Complete Locus Pairs**: Both allele partner columns (`_A1` and `_A2`) must be present for every locus. If a partner column is missing (e.g. `Locus1_A1` exists without `Locus1_A2`), the server returns an HTTP 400 JSON error.
2. **Pairwise Missing Call Handling**: Blank or missing genotype calls (`""`, `NA`, `NaN`, `null`, `.`, `-9`) are evaluated pairwise. If either allele call in a diploid pair is missing for a given individual, that locus call is omitted for that individual. Individuals with missing calls at one locus are retained for other complete loci.
3. **Empty Locus Rejection**: If a locus has zero complete genotype calls across all individuals, the server rejects the upload with an HTTP 400 JSON error.
4. **Categorical Allele Representation**: Numeric allele labels (e.g., `142`, `150`) and alphanumeric alleles (e.g., `A`, `B`) are treated strictly as discrete categorical identifiers, preventing numeric coercion or floating-point rounding errors.
5. **Payload Limits**: Uploaded files are capped at 4 MB (aligned with Vercel's 4.5 MB serverless limit). Client-side validation validates file size and `.csv` extensions before upload.
6. **Data Privacy & Security**: Uploaded files are processed strictly in memory and are never persisted to disk. Server logs do not record individual IDs, allele genotypes, or row contents.

---

## 3. Mathematical Calculations & Screening Rules

### 1. Per-Locus Heterozygosity
For a locus with $N$ complete diploid individuals ($2N$ pooled alleles):
- **Observed Heterozygosity ($H_o$)**: The fraction of complete individuals whose two alleles differ ($A_1 \neq A_2$):
  $$H_o = \frac{\sum_{j=1}^N \mathbf{1}(A_{1,j} \neq A_{2,j})}{N}$$
- **Expected Heterozygosity ($H_e$)**: Calculated using Hardy-Weinberg expectations after pooling all alleles for that locus:
  $$H_e = 1 - \sum_{i=1}^k p_i^2$$
  where $p_i$ is the frequency of allele $i$ across the $2N$ pooled alleles:
  $$p_i = \frac{\text{count}(i)}{2N}$$

### 2. Multi-Locus Summary Statistics
Across $L$ evaluated loci:
- **Mean Observed Heterozygosity**: $\overline{H_o} = \frac{1}{L} \sum_{l=1}^L H_{o,l}$
- **Mean Expected Heterozygosity**: $\overline{H_e} = \frac{1}{L} \sum_{l=1}^L H_{e,l}$
- **Inbreeding Coefficient ($F_{is}$)**:
  $$F_{is} = \frac{\overline{H_e} - \overline{H_o}}{\overline{H_e}}$$
  *Zero-Variance Edge Case*: If $\overline{H_e} = 0$ (all loci monomorphic), $F_{is}$ returns JSON `null` and displays as `N/A` in the interface to prevent division-by-zero, `NaN`, or `Infinity`.

### 3. Population Classification Hierarchy
Screening status is assigned strictly in the following priority order:

1. **`CRITICAL` (Accent Token: `red`)**:
   - **Condition**: $\overline{H_o} > \overline{H_e}$
   - **Interpretation**: Heterozygosity excess. This screening pattern is consistent with a possible recent population bottleneck (where rare alleles are lost faster than overall heterozygosity).
   - **Important Scientific Caveat**: This heuristic alone does not confirm a demographic bottleneck. Formal verification requires testing against expected heterozygosity conditioned on observed allele numbers ($H_{eq}$) under appropriate mutation-drift models (e.g. IAM, SMM, or TPM; Cornuet & Luikart 1996).
2. **`WARNING` (Accent Token: `yellow`)**:
   - **Condition**: $F_{is} > 0.15$ (with $\overline{H_o} \le \overline{H_e}$)
   - **Interpretation**: Heterozygosity deficit. Indicates elevated homozygosity, which may reflect inbreeding, population substructure (Wahlund effect), or demographic isolation.
3. **`STABLE` (Accent Token: `green`)**:
   - **Condition**: Otherwise ($F_{is} \le 0.15$ and $\overline{H_o} \le \overline{H_e}$)
   - **Interpretation**: Genotype proportions align with baseline Hardy-Weinberg expectations under this screening rule. Note that simple summary thresholds cannot rule out underlying conservation or demographic concerns.

---

## 4. Local Development & Testing

### Prerequisites
- Python 3.10+
- Dependencies: `Flask==3.0.3`, `pandas==2.2.2`, `Werkzeug==3.0.3`

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Running Tests
Execute the comprehensive test suite (unit tests and API integration tests):
```bash
python3 run_tests.py
```
Or run individual test modules:
```bash
python3 tests/test_analysis.py
python3 tests/test_api.py
```

### Running Locally with Flask
To start a local development server:
```bash
python3 -c "from api.index import app; app.run(host='127.0.0.1', port=5000, debug=True)"
```
Then visit `http://127.0.0.1:5000/` or access the API directly:
```bash
curl http://127.0.0.1:5000/api/health
```

---

## 5. Vercel Deployment Guide

### Project Directory Structure
```
ecogen-diagnostics/
├── api/
│   ├── __init__.py
│   ├── analysis.py        # Core bioinformatics engine & validations
│   └── index.py           # Vercel Flask entrypoint exporting `app`
├── public/
│   ├── index.html         # Accessible dark scientific single-page UI
│   ├── app.js             # Client controller with diagnostic error parsing
│   └── style.css          # Tailwind extensions, contrast & reduced motion
├── tests/
│   ├── test_analysis.py   # Unit test suite
│   └── test_api.py        # API endpoint integration tests
├── requirements.txt       # Pinned dependencies for Vercel Python runtime
├── vercel.json            # API routing and rewrites
├── run_tests.py           # Unified test runner
└── README.md
```

### Deploying to Vercel
1. Install Vercel CLI (optional):
   ```bash
   npm install -g vercel
   ```
2. Deploy the project:
   ```bash
   vercel
   ```
   Or connect your GitHub repository to Vercel:
   - Framework Preset: **Other**
   - Root Directory: `./`
   - Output Directory: Automatically detected as `public/`
   - Vercel automatically detects `requirements.txt` and provisions the Python serverless runtime for `api/index.py`.

### Verifying Deployment
Test the live health endpoint:
```bash
curl https://<your-deployment-url>.vercel.app/api/health
```
Expected response:
```json
{"ok": true, "service": "EcoGen Diagnostics"}
```

---

## 6. Troubleshooting Checklist

| Symptom | Probable Cause | Recommended Action |
| :--- | :--- | :--- |
| **"The analysis service returned an unreadable response"** | Client attempted `response.json()` on an HTML 404 or 500 page. | Update client to inspect HTTP status and `Content-Type` before parsing (implemented in `public/app.js`). |
| **`GET /api/health` returns 404 HTML** | Vercel rewrite rule missing or route shadowed by static catch-all. | Ensure `vercel.json` has `{"source": "/api/(.*)", "destination": "/api/index.py"}`. |
| **`POST /api/upload` returns 405 Method Not Allowed** | Endpoint missing POST decorator or static server intercepted request. | Verify `@app.route('/api/upload', methods=['POST'])` in `api/index.py`. |
| **HTTP 413 Payload Too Large** | Uploaded file exceeds 4 MB. | Reduce CSV file size or compress whitespace. |
| **HTTP 400 "Missing required partner column"** | CSV contains an unpaired locus column (e.g. `Locus1_A1` without `Locus1_A2`). | Ensure every locus has both diploid allele columns `_A1` and `_A2`. |
| **HTTP 500 Function Invocation Error** | Missing dependency or unhandled exception during import. | Inspect Vercel Function logs in the Vercel Dashboard for Python traceback. |
