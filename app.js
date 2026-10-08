/**
 * EcoGen Diagnostics — Frontend Controller
 * Plain browser JavaScript with accessible DOM manipulation, safe text rendering,
 * and robust diagnostic error handling.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const uploadSection = document.getElementById('uploadSection');
  const selectedFileInfo = document.getElementById('selectedFileInfo');
  const selectedFileName = document.getElementById('selectedFileName');
  const selectedFileSize = document.getElementById('selectedFileSize');
  const uploadButton = document.getElementById('uploadButton');
  
  const loadingState = document.getElementById('loadingState');
  const errorState = document.getElementById('errorState');
  const errorTitle = document.getElementById('errorTitle');
  const errorMessage = document.getElementById('errorMessage');
  const errorDetailsBox = document.getElementById('errorDetailsBox');
  const errorNextStepBox = document.getElementById('errorNextStepBox');
  const errorNextStepText = document.getElementById('errorNextStepText');
  const tryAgainButton = document.getElementById('tryAgainButton');
  
  const resultsState = document.getElementById('resultsState');
  const statusBanner = document.getElementById('statusBanner');
  const statusBadge = document.getElementById('statusBadge');
  const verdictText = document.getElementById('verdictText');
  const disclaimerText = document.getElementById('disclaimerText');
  const metricHo = document.getElementById('metricHo');
  const metricHe = document.getElementById('metricHe');
  const metricFis = document.getElementById('metricFis');
  const metricSamples = document.getElementById('metricSamples');
  const metricLoci = document.getElementById('metricLoci');
  const locusTableBody = document.getElementById('locusTableBody');
  const resetButton = document.getElementById('resetButton');
  
  const healthDot = document.getElementById('healthDot');
  const healthText = document.getElementById('healthText');
  const ariaLiveAnnouncer = document.getElementById('ariaLiveAnnouncer');

  const MAX_FILE_SIZE_BYTES = 4 * 1024 * 1024; // 4 MB limit (Vercel has 4.5 MB request limit)
  let currentSelectedFile = null;

  // Announce messages to screen readers
  function announce(message) {
    if (ariaLiveAnnouncer) {
      ariaLiveAnnouncer.textContent = message;
    }
  }

  // Format file size nicely
  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // Check Backend Health on Startup
  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      const contentType = res.headers.get('content-type') || '';
      
      if (res.ok && contentType.includes('application/json')) {
        const data = await res.json();
        if (data && data.ok) {
          healthDot.className = 'w-2 h-2 rounded-full bg-emerald-400 mr-1.5';
          healthText.textContent = 'Backend: Online';
          return;
        }
      }
      // If response is not ok or not JSON
      healthDot.className = 'w-2 h-2 rounded-full bg-amber-400 mr-1.5';
      healthText.textContent = `Backend: HTTP ${res.status}`;
    } catch (err) {
      healthDot.className = 'w-2 h-2 rounded-full bg-red-400 mr-1.5';
      healthText.textContent = 'Backend: Unreachable';
    }
  }

  checkHealth();

  // Reset to initial clean state
  function resetUI() {
    currentSelectedFile = null;
    fileInput.value = '';
    selectedFileInfo.classList.add('hidden');
    selectedFileInfo.classList.remove('flex');
    uploadSection.classList.remove('hidden');
    loadingState.classList.add('hidden');
    errorState.classList.add('hidden');
    resultsState.classList.add('hidden');
    announce('Analysis view reset. Ready to upload a new dataset.');
  }

  // Show detailed error state
  function showError(opts) {
    loadingState.classList.add('hidden');
    resultsState.classList.add('hidden');
    errorState.classList.remove('hidden');

    errorTitle.textContent = opts.title || 'Analysis Error';
    errorMessage.textContent = opts.message || 'An error occurred during dataset processing.';

    if (opts.details) {
      errorDetailsBox.textContent = opts.details;
      errorDetailsBox.classList.remove('hidden');
    } else {
      errorDetailsBox.classList.add('hidden');
      errorDetailsBox.textContent = '';
    }

    if (opts.nextStep) {
      errorNextStepText.textContent = opts.nextStep;
      errorNextStepBox.classList.remove('hidden');
    } else {
      errorNextStepBox.classList.add('hidden');
      errorNextStepText.textContent = '';
    }

    announce(`Error: ${errorTitle.textContent}. ${errorMessage.textContent}`);
  }

  // Render Analysis Results
  function renderResults(data) {
    loadingState.classList.add('hidden');
    errorState.classList.add('hidden');
    uploadSection.classList.add('hidden');
    resultsState.classList.remove('hidden');

    const summary = data.summary || {};
    const status = data.status || 'UNKNOWN';
    const color = (data.color || 'yellow').toLowerCase();

    // Configure status banner styling based on semantic color token
    statusBanner.className = 'p-6 rounded-xl border shadow-md space-y-4';
    statusBadge.className = 'px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase border';

    if (color === 'red') {
      statusBanner.classList.add('bg-red-950/20', 'border-red-800/40');
      statusBadge.classList.add('bg-red-500/15', 'text-red-300', 'border-red-500/30');
    } else if (color === 'yellow') {
      statusBanner.classList.add('bg-amber-950/20', 'border-amber-800/40');
      statusBadge.classList.add('bg-amber-500/15', 'text-amber-300', 'border-amber-500/30');
    } else {
      statusBanner.classList.add('bg-emerald-950/20', 'border-emerald-800/40');
      statusBadge.classList.add('bg-emerald-500/15', 'text-emerald-300', 'border-emerald-500/30');
    }

    statusBadge.textContent = status;
    verdictText.textContent = data.verdict || '';
    disclaimerText.textContent = ' ' + (data.disclaimer || '');

    // Format metrics to 4 decimal places
    metricHo.textContent = typeof summary.ho === 'number' ? summary.ho.toFixed(4) : '--';
    metricHe.textContent = typeof summary.he === 'number' ? summary.he.toFixed(4) : '--';
    metricFis.textContent = (summary.fis === null || summary.fis === undefined) ? 'N/A' : (typeof summary.fis === 'number' ? summary.fis.toFixed(4) : String(summary.fis));
    metricSamples.textContent = summary.sample_count !== undefined ? summary.sample_count : '--';
    metricLoci.textContent = summary.locus_count !== undefined ? summary.locus_count : '--';

    // Populate Per-Locus Table
    locusTableBody.innerHTML = '';
    const loci = data.loci || [];
    if (loci.length === 0) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 5;
      cell.className = 'py-4 px-4 text-center text-slate-400 font-sans';
      cell.textContent = 'No locus breakdown available.';
      row.appendChild(cell);
      locusTableBody.appendChild(row);
    } else {
      loci.forEach(l => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-800/50 transition-colors';

        const cellLocus = document.createElement('td');
        cellLocus.className = 'py-3 px-4 font-semibold text-cyan-400';
        cellLocus.textContent = l.locus || 'Locus';

        const cellSamples = document.createElement('td');
        cellSamples.className = 'py-3 px-4 text-slate-300';
        cellSamples.textContent = l.samples_analyzed !== undefined ? l.samples_analyzed : '--';

        const cellMissing = document.createElement('td');
        cellMissing.className = 'py-3 px-4 text-slate-400';
        cellMissing.textContent = l.missing_count !== undefined ? l.missing_count : 0;

        const cellHo = document.createElement('td');
        cellHo.className = 'py-3 px-4 text-slate-200';
        cellHo.textContent = typeof l.ho === 'number' ? l.ho.toFixed(4) : '--';

        const cellHe = document.createElement('td');
        cellHe.className = 'py-3 px-4 text-slate-200';
        cellHe.textContent = typeof l.he === 'number' ? l.he.toFixed(4) : '--';

        row.appendChild(cellLocus);
        row.appendChild(cellSamples);
        row.appendChild(cellMissing);
        row.appendChild(cellHo);
        row.appendChild(cellHe);
        locusTableBody.appendChild(row);
      });
    }

    announce(`Analysis complete. Status: ${status}. Mean Ho: ${metricHo.textContent}, Mean He: ${metricHe.textContent}, Fis: ${metricFis.textContent}.`);
  }

  // Validate file selection before submission
  function handleFileSelected(file) {
    if (!file) return;

    // Check extension
    if (!file.name.toLowerCase().endsWith('.csv')) {
      showError({
        title: 'Invalid File Extension',
        message: `The file "${file.name}" is not a CSV file. EcoGen Diagnostics requires a .csv file format.`,
        nextStep: 'Please select a comma-separated values file ending in .csv.'
      });
      return;
    }

    // Check file size
    if (file.size === 0) {
      showError({
        title: 'Empty File',
        message: `The file "${file.name}" is 0 bytes and contains no data.`,
        nextStep: 'Please select a populated CSV file containing genotype records.'
      });
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      showError({
        title: 'File Exceeds Upload Limit',
        message: `File size (${formatBytes(file.size)}) exceeds the maximum allowed size of 4 MB.`,
        nextStep: 'Reduce the dataset size or compress whitespace before uploading.'
      });
      return;
    }

    // Valid file selected
    currentSelectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = formatBytes(file.size);
    selectedFileInfo.classList.remove('hidden');
    selectedFileInfo.classList.add('flex');
    errorState.classList.add('hidden');
    announce(`Selected file ${file.name}, size ${formatBytes(file.size)}. Click Run Analysis to proceed.`);
  }

  // Execute Analysis Upload
  async function performUpload() {
    if (!currentSelectedFile) {
      showError({
        title: 'No File Selected',
        message: 'Please choose or drop a valid CSV dataset before running analysis.',
        nextStep: 'Select a CSV file using the file chooser or drag-and-drop zone.'
      });
      return;
    }

    // Transition to loading state
    uploadSection.classList.add('hidden');
    errorState.classList.add('hidden');
    resultsState.classList.add('hidden');
    loadingState.classList.remove('hidden');
    announce('Uploading dataset and computing population genetics metrics...');

    const formData = new FormData();
    formData.append('file', currentSelectedFile);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      const contentType = response.headers.get('content-type') || '';
      const status = response.status;
      const statusText = response.statusText || '';

      // Safe evaluation of response content type
      if (contentType.includes('application/json')) {
        let data;
        try {
          data = await response.json();
        } catch (jsonErr) {
          showError({
            title: `JSON Parse Failure (HTTP ${status})`,
            message: 'Server advertised application/json content-type but returned malformed JSON.',
            details: `HTTP Status: ${status} ${statusText}\nParse error: ${jsonErr.message}`,
            nextStep: 'Verify server logs in Vercel Function logs to check for truncated output or serialization errors.'
          });
          return;
        }

        if (!response.ok) {
          // Server returned structured JSON error
          showError({
            title: `Validation Error (HTTP ${status})`,
            message: data.error || 'Server rejected the dataset with an unspecified error.',
            nextStep: 'Review the CSV column headers and ensure all loci have paired _A1 and _A2 columns with valid calls.'
          });
          return;
        }

        // Render successful results
        renderResults(data);

      } else {
        // Non-JSON response received (HTML error page, Vercel 404, or gateway timeout)
        const rawText = await response.text();
        const snippet = rawText.slice(0, 350).trim();

        let diagnosticNextStep = 'Check Vercel deployment configuration, API rewrites, and serverless function logs.';
        if (status === 404) {
          diagnosticNextStep = 'The /api/upload endpoint returned 404 Not Found. Ensure vercel.json includes a rewrite routing /api/(.*) to api/index.py, and that the Python function deployed successfully.';
        } else if (status === 405) {
          diagnosticNextStep = 'The server returned 405 Method Not Allowed. Ensure the /api/upload endpoint in api/index.py explicitly allows POST requests.';
        } else if (status === 413) {
          diagnosticNextStep = 'The payload exceeded Vercel request limits (4.5 MB). Upload a smaller dataset.';
        } else if (status >= 500) {
          diagnosticNextStep = 'The Python function failed during execution or initialization. Inspect Vercel Function Logs in the dashboard for Python exceptions or missing dependencies.';
        }

        showError({
          title: `Non-JSON Response (HTTP ${status} ${statusText})`,
          message: `The analysis service returned an unexpected content type (${contentType || 'None'}).`,
          details: `HTTP Status: ${status} ${statusText}\nContent-Type: ${contentType || 'None'}\n\nResponse Preview:\n${snippet ? snippet + (rawText.length > 350 ? '...' : '') : '(Empty response body)'}`,
          nextStep: diagnosticNextStep
        });
      }

    } catch (networkErr) {
      showError({
        title: 'Network Communication Error',
        message: 'Could not connect to the EcoGen analysis backend service.',
        details: `Network Error: ${networkErr.message || 'Connection failed'}`,
        nextStep: 'Verify your internet connection and check if the Vercel deployment is active.'
      });
    }
  }

  // Event Listeners for Drag and Drop
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      handleFileSelected(dt.files[0]);
    }
  });

  // Dropzone click & keyboard access
  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  uploadButton.addEventListener('click', () => {
    performUpload();
  });

  tryAgainButton.addEventListener('click', () => {
    resetUI();
  });

  resetButton.addEventListener('click', () => {
    resetUI();
  });
});
