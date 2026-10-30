/**
 * The Daily Pulse (PulsePersona) - Frontend Application Logic
 * Implements Step 30 (Persona Selector UI & Detailed Modal Dialog) and Step 31 (Feed Results & Insight Display)
 * Styled in the visual theme of Jagran: Clean, modern Indian newspaper aesthetic (100% English, zero emojis).
 */

const API_BASE_URL = window.location.origin.includes(':8000') 
  ? window.location.origin 
  : 'http://localhost:8000';

let allPersonas = [];
let currentPersonaId = 'tech_professional';
let activeModalPersonaId = null;
let isRefreshing = false;

/**
 * Utility: Strips any emoji or surrogate pair characters from any text string
 */
function stripEmojis(text) {
  if (!text) return '';
  return String(text)
    .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F1E6}-\u{1F1FF}]/gu, '')
    .trim();
}

// Fallback Mock Personas in case backend is offline during preview
const FALLBACK_PERSONAS = [
  {
    "persona_id": "tech_professional",
    "name": "Tech Professional",
    "description": "Software engineers, IT professionals, and tech industry workers who want to stay current on their field.",
    "topics": [
      { "keyword": "artificial intelligence", "weight": 0.9 },
      { "keyword": "software engineering", "weight": 0.85 },
      { "keyword": "startups", "weight": 0.7 },
      { "keyword": "cybersecurity", "weight": 0.75 },
      { "keyword": "big tech companies", "weight": 0.8 }
    ],
    "exclude_topics": ["celebrity gossip", "sports"],
    "tone": "professional, concise",
    "reading_level": "advanced",
    "depth": "summary"
  },
  {
    "persona_id": "college_student",
    "name": "College Student",
    "description": "Students interested in campus life, careers, and light general news in simple language.",
    "topics": [
      { "keyword": "campus life", "weight": 0.7 },
      { "keyword": "career and jobs", "weight": 0.8 },
      { "keyword": "exams and education", "weight": 0.75 },
      { "keyword": "scholarships", "weight": 0.6 }
    ],
    "exclude_topics": ["complex finance", "economic policy jargon"],
    "tone": "casual, simple",
    "reading_level": "beginner",
    "depth": "summary"
  },
  {
    "persona_id": "finance_markets",
    "name": "Finance & Markets Enthusiast",
    "description": "Investors and finance-minded readers who track markets, economy, and business news closely.",
    "topics": [
      { "keyword": "stock markets", "weight": 0.9 },
      { "keyword": "economy", "weight": 0.85 },
      { "keyword": "RBI monetary policy", "weight": 0.8 },
      { "keyword": "startups and IPOs", "weight": 0.75 }
    ],
    "exclude_topics": ["entertainment", "sports"],
    "tone": "analytical, data-driven",
    "reading_level": "advanced",
    "depth": "detailed"
  }
];

// DOM Element References
const personaGrid = document.getElementById('personaGrid');
const feedSection = document.getElementById('feedSection');
const feedLoading = document.getElementById('feedLoading');
const feedError = document.getElementById('feedError');
const errorTitle = document.getElementById('errorTitle');
const errorMessage = document.getElementById('errorMessage');
const generateNowBtn = document.getElementById('generateNowBtn');
const currentDateStr = document.getElementById('currentDateStr');
const mastheadRefreshBtn = document.getElementById('mastheadRefreshBtn');
const heroRefreshBtn = document.getElementById('heroRefreshBtn');

// Feed Header & Insight Elements
const activePersonaName = document.getElementById('activePersonaName');
const activePersonaDesc = document.getElementById('activePersonaDesc');
const feedWeekDate = document.getElementById('feedWeekDate');
const statArticleCount = document.getElementById('statArticleCount');
const statCategoryCount = document.getElementById('statCategoryCount');
const weeklyInsightText = document.getElementById('weeklyInsightText');
const feedCategoriesContainer = document.getElementById('feedCategoriesContainer');
const toastContainer = document.getElementById('toastContainer');

// Modal Elements
const personaModal = document.getElementById('personaModal');
const modalCloseBtn = document.getElementById('modalCloseBtn');
const modalApplyBtn = document.getElementById('modalApplyBtn');
const modalProfileIndex = document.getElementById('modalProfileIndex');
const modalActiveStatus = document.getElementById('modalActiveStatus');
const modalPersonaTitle = document.getElementById('modalPersonaTitle');
const modalPersonaDesc = document.getElementById('modalPersonaDesc');
const modalTone = document.getElementById('modalTone');
const modalReadingLevel = document.getElementById('modalReadingLevel');
const modalDepth = document.getElementById('modalDepth');
const modalTopicsList = document.getElementById('modalTopicsList');
const modalExcludeBox = document.getElementById('modalExcludeBox');
const modalExcludeList = document.getElementById('modalExcludeList');


/**
 * Initializes the application on page load
 */
async function initApp() {
  updateCurrentDate();
  setupEventListeners();
  await loadPersonas();
}


/**
 * Formats current date for the top newspaper dateline (English)
 */
function updateCurrentDate() {
  if (!currentDateStr) return;
  const now = new Date();
  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  currentDateStr.textContent = `${now.toLocaleDateString('en-US', options)} | New Delhi`;
}


/**
 * Sets up UI event listeners
 */
function setupEventListeners() {
  if (generateNowBtn) {
    generateNowBtn.addEventListener('click', () => {
      triggerFeedRefresh(currentPersonaId);
    });
  }

  if (mastheadRefreshBtn) {
    mastheadRefreshBtn.addEventListener('click', (e) => {
      e.preventDefault();
      triggerFeedRefresh(currentPersonaId);
    });
  }

  if (heroRefreshBtn) {
    heroRefreshBtn.addEventListener('click', (e) => {
      e.preventDefault();
      triggerFeedRefresh(currentPersonaId);
    });
  }

  // Modal event listeners
  if (modalCloseBtn && personaModal) {
    modalCloseBtn.addEventListener('click', () => {
      closePersonaModal();
    });
  }

  if (personaModal) {
    // Backdrop click close
    personaModal.addEventListener('click', (e) => {
      if (e.target === personaModal) {
        closePersonaModal();
      }
    });

    // Escape key close
    personaModal.addEventListener('cancel', () => {
      closePersonaModal();
    });
  }

  if (modalApplyBtn) {
    modalApplyBtn.addEventListener('click', () => {
      if (activeModalPersonaId) {
        selectPersona(activeModalPersonaId);
        closePersonaModal();
        if (feedSection) {
          feedSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  }
}


/**
 * Step 30: Fetches all curated reader personas from API (with graceful fallback)
 */
async function loadPersonas() {
  try {
    const response = await fetch(`${API_BASE_URL}/personas`);
    if (!response.ok) {
      throw new Error(`Failed to load personas: ${response.statusText}`);
    }

    allPersonas = await response.json();
    renderPersonaSelector(allPersonas);

    // Default to tech_professional or first persona
    const defaultPersona = allPersonas.find(p => p.persona_id === currentPersonaId) || allPersonas[0];
    if (defaultPersona) {
      selectPersona(defaultPersona.persona_id);
    }
  } catch (error) {
    console.warn('API unavailable, rendering fallback personas for UI preview:', error);
    allPersonas = FALLBACK_PERSONAS;
    renderPersonaSelector(allPersonas);
    selectPersona(allPersonas[0].persona_id);
  }
}


/**
 * Step 30: Renders the Persona Selection Grid (100% clean typographic broadsheet style, zero emojis)
 */
function renderPersonaSelector(personas) {
  if (!personaGrid) return;
  personaGrid.innerHTML = '';

  personas.forEach((persona, index) => {
    const indexNum = String(index + 1).padStart(2, '0');
    const cleanName = stripEmojis(persona.name);
    const cleanDesc = stripEmojis(persona.description);

    // Extract Topic Keywords
    const topicKeywords = (persona.topics || []).map(t => {
      if (typeof t === 'string') return stripEmojis(t);
      if (typeof t === 'object' && t.keyword) return stripEmojis(t.keyword);
      return stripEmojis(String(t));
    }).filter(Boolean).slice(0, 3);

    // Create Newspaper Persona Card
    const card = document.createElement('div');
    card.className = `persona-card ${persona.persona_id === currentPersonaId ? 'active' : ''}`;
    card.id = `card-${persona.persona_id}`;
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', `View full persona profile for ${cleanName}`);

    card.innerHTML = `
      <div class="persona-card-content">
        <div class="persona-card-header">
          <span class="persona-index-badge">Profile ${indexNum}</span>
          <h3 class="persona-card-title">${escapeHtml(cleanName)}</h3>
        </div>
        <p class="persona-card-desc">${escapeHtml(cleanDesc)}</p>
      </div>
      
      <div>
        <div class="persona-topic-tags">
          ${topicKeywords.map(topic => `<span class="topic-tag">${escapeHtml(topic)}</span>`).join('')}
        </div>
        <div class="persona-card-action">
          <span class="view-profile-link">
            <span>View Full Persona Specs</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </span>
        </div>
      </div>
    `;

    // Clicking card opens the detailed modal dialog
    card.addEventListener('click', () => {
      openPersonaModal(persona, indexNum);
    });

    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openPersonaModal(persona, indexNum);
      }
    });

    personaGrid.appendChild(card);
  });
}


/**
 * Opens the comprehensive persona specification dialog box
 */
function openPersonaModal(persona, indexNum) {
  if (!personaModal) return;
  activeModalPersonaId = persona.persona_id;

  const isCurrentActive = persona.persona_id === currentPersonaId;
  const cleanName = stripEmojis(persona.name);
  const cleanDesc = stripEmojis(persona.description);

  if (modalProfileIndex) modalProfileIndex.textContent = `PROFILE ${indexNum} SPECIFICATION`;
  if (modalActiveStatus) {
    modalActiveStatus.textContent = isCurrentActive ? 'CURRENT ACTIVE SELECTION' : 'AVAILABLE PROFILE';
    modalActiveStatus.className = `modal-status-badge ${isCurrentActive ? 'is-active' : ''}`;
  }

  if (modalPersonaTitle) modalPersonaTitle.textContent = cleanName;
  if (modalPersonaDesc) modalPersonaDesc.textContent = cleanDesc;

  if (modalTone) modalTone.textContent = persona.tone || 'Professional, Balanced';
  if (modalReadingLevel) modalReadingLevel.textContent = persona.reading_level || 'Advanced';
  if (modalDepth) modalDepth.textContent = persona.depth || 'Summary';

  // Render Topic Focus with Weights
  if (modalTopicsList) {
    modalTopicsList.innerHTML = '';
    const topics = persona.topics || [];
    if (topics.length === 0) {
      modalTopicsList.innerHTML = '<span style="color: var(--text-muted); font-size: 0.9rem;">No specific topic weights declared.</span>';
    } else {
      topics.forEach(t => {
        const topicName = stripEmojis(typeof t === 'string' ? t : (t.keyword || t.name || 'General'));
        const weight = typeof t === 'object' && t.weight !== undefined ? t.weight : 0.7;
        const percent = Math.round(weight * 100);

        const row = document.createElement('div');
        row.className = 'topic-weight-item';
        row.innerHTML = `
          <div class="topic-weight-info">
            <span class="topic-weight-name">${escapeHtml(topicName)}</span>
            <span class="topic-weight-val">${percent}% Focus</span>
          </div>
          <div class="topic-weight-bar-bg">
            <div class="topic-weight-bar-fill" style="width: ${percent}%"></div>
          </div>
        `;
        modalTopicsList.appendChild(row);
      });
    }
  }

  // Render Excluded Topics
  if (modalExcludeList && modalExcludeBox) {
    const excludes = persona.exclude_topics || [];
    if (excludes.length === 0) {
      modalExcludeBox.style.display = 'none';
    } else {
      modalExcludeBox.style.display = 'block';
      modalExcludeList.innerHTML = excludes
        .map(ex => `<span class="exclude-tag">${escapeHtml(stripEmojis(ex))}</span>`)
        .join('');
    }
  }

  // Update apply button text
  if (modalApplyBtn) {
    modalApplyBtn.textContent = isCurrentActive 
      ? 'Viewing Weekly News Feed for this Persona' 
      : `Select ${cleanName} & Load Weekly Feed`;
  }

  // Show modal dialog
  if (typeof personaModal.showModal === 'function') {
    personaModal.showModal();
  } else {
    personaModal.setAttribute('open', '');
  }

  // Lock background scroll
  document.body.style.overflow = 'hidden';
}


/**
 * Closes the persona dialog
 */
function closePersonaModal() {
  if (!personaModal) return;
  if (typeof personaModal.close === 'function') {
    personaModal.close();
  } else {
    personaModal.removeAttribute('open');
  }
  document.body.style.overflow = '';
}


/**
 * Handles selecting an active persona
 */
function selectPersona(personaId) {
  currentPersonaId = personaId;

  // Update active state in Persona Cards
  document.querySelectorAll('.persona-card').forEach(card => {
    card.classList.remove('active');
  });

  const activeCard = document.getElementById(`card-${personaId}`);
  if (activeCard) {
    activeCard.classList.add('active');
  }

  // Fetch and display feed
  fetchWeeklyFeed(personaId);
}


/**
 * Step 31: Fetches the pre-generated weekly news feed for a persona
 */
async function fetchWeeklyFeed(personaId) {
  showLoading(true, personaId);
  hideError();
  if (feedSection) feedSection.classList.add('hidden');

  try {
    const response = await fetch(`${API_BASE_URL}/feed/${personaId}`);

    if (response.status === 404) {
      showLoading(false);
      renderPipelineError({
        error_title: 'Weekly Edition Not Yet Compiled',
        error_message: `The weekly news broadsheet for '${personaId}' has not been generated yet.`,
        recovery_hint: 'Click "Generate Feed Now" below to run the multi-agent pipeline and assemble key stories.',
        failed_agent: 'Feed Cache Desk',
        failed_engine: 'Local Storage'
      }, personaId);
      return;
    }

    if (!response.ok) {
      throw new Error(`Failed to load feed: ${response.statusText}`);
    }

    const feedData = await response.json();
    renderFeedResults(feedData);
    showLoading(false);
    if (feedSection) feedSection.classList.remove('hidden');

  } catch (error) {
    console.error('Error loading weekly feed:', error);
    showLoading(false);
    renderPipelineError({
      error_title: 'Unable to Contact Backend Server',
      error_message: `Could not connect to API server at ${API_BASE_URL}.`,
      recovery_hint: 'Please ensure the FastAPI backend is running via run_project.bat in the terminal.',
      failed_agent: 'API Network Gateway',
      failed_engine: 'HTTP Protocol',
      error_details: error.stack || String(error)
    }, personaId);
  }
}


/**
 * Step 31: Renders the Weekly Results Display with Editorial Insight Banner and Categorized Articles
 */
function renderFeedResults(feed) {
  // 1. Update Hero Details with stripped emojis
  if (activePersonaName) activePersonaName.textContent = stripEmojis(feed.persona_name) || 'Personalized News';
  if (activePersonaDesc) activePersonaDesc.textContent = stripEmojis(feed.persona_description) || 'Curated weekly stories and strategic executive insights.';
  
  if (feedWeekDate && feed.week_start_date && feed.week_end_date) {
    feedWeekDate.textContent = `Weekly Edition: ${formatDate(feed.week_start_date)} – ${formatDate(feed.week_end_date)}`;
  }

  if (statArticleCount) statArticleCount.textContent = feed.total_articles || 0;
  if (statCategoryCount) statCategoryCount.textContent = feed.total_categories || (feed.categories ? feed.categories.length : 0);

  // 2. Render Gemini Executive Weekly Synthesis Insight
  if (weeklyInsightText) {
    weeklyInsightText.textContent = feed.weekly_insight || 'No synthesis recorded for this weekly period.';
  }

  // 3. Render Categorized Article Cards with Bullets (2 per row in grid)
  if (!feedCategoriesContainer) return;
  feedCategoriesContainer.innerHTML = '';

  const categories = feed.categories || [];
  if (categories.length === 0) {
    feedCategoriesContainer.innerHTML = `
      <div class="empty-feed-notice">
        No articles found for this weekly edition.
      </div>
    `;
    return;
  }

  categories.forEach(category => {
    const categoryGroup = document.createElement('div');
    categoryGroup.className = 'category-group';

    const articles = category.articles || [];
    const cleanCategoryTopic = stripEmojis(category.topic);

    categoryGroup.innerHTML = `
      <div class="category-header">
        <h3 class="category-title">${escapeHtml(cleanCategoryTopic)}</h3>
        <span class="category-count-badge">${articles.length} stories</span>
      </div>
      <div class="articles-grid">
        ${articles.map(article => renderArticleCardHtml(article)).join('')}
      </div>
    `;

    feedCategoriesContainer.appendChild(categoryGroup);
  });
}


/**
 * Generates HTML for an individual Article Card with simple English bullets
 */
function renderArticleCardHtml(article) {
  const bullets = article.bullets || [];
  const relevancePercent = Math.round((article.relevance_score || 0.7) * 100);
  const readTime = article.read_time_minutes || 1;
  const sourceName = stripEmojis(article.source) || 'Verified Source';
  const cleanTitle = stripEmojis(article.title);

  return `
    <article class="article-card">
      <div class="article-header">
        <div class="article-meta-row">
          <span class="source-tag">${escapeHtml(sourceName)}</span>
          <span class="score-badge" title="AI Relevance Match: ${relevancePercent}%">${relevancePercent}% Match</span>
        </div>
        <h4 class="article-title">${escapeHtml(cleanTitle)}</h4>
      </div>

      <ul class="article-bullets-list">
        ${bullets.map(bullet => `<li>${escapeHtml(stripEmojis(bullet))}</li>`).join('')}
      </ul>

      <div class="article-footer">
        <div class="read-time-pill">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>${readTime} min read</span>
        </div>
        <a href="${escapeHtml(article.url)}" target="_blank" rel="noopener noreferrer" class="article-outbound-link">
          <span>Read Source</span>
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </a>
      </div>
    </article>
  `;
}


/**
 * Refresh Feed Functionality:
 * Triggers the pipeline via POST /feed/${personaId}/refresh or POST /admin/run-weekly
 */
/**
 * Real-Time Pipeline Telemetry Poller & Terminal Synchronizer
 */
let pipelineTelemetryInterval = null;
let pipelineStartTime = null;

function startPipelinePolling(personaId, onCompleted, onError) {
  stopPipelinePolling();
  pipelineStartTime = Date.now();

  // Initial immediate fetch
  pollPipelineTelemetry(personaId, onCompleted, onError);

  // Poll every 550ms for smooth real-time synchronization with terminal execution
  pipelineTelemetryInterval = setInterval(() => {
    pollPipelineTelemetry(personaId, onCompleted, onError);
  }, 550);
}

function stopPipelinePolling() {
  if (pipelineTelemetryInterval) {
    clearInterval(pipelineTelemetryInterval);
    pipelineTelemetryInterval = null;
  }
}

async function pollPipelineTelemetry(personaId, onCompleted, onError) {
  try {
    const res = await fetch(`${API_BASE_URL}/pipeline/status/${personaId}`);
    if (!res.ok) return;

    const data = await res.json();
    updatePipelineTelemetryUI(data);

    if (data.status === 'completed') {
      stopPipelinePolling();
      if (typeof onCompleted === 'function') onCompleted(data);
    } else if (data.status === 'error') {
      stopPipelinePolling();
      if (typeof onError === 'function') {
        onError(data.error || data);
      } else {
        renderPipelineError(data.error || data, personaId);
      }
    }
  } catch (err) {
    console.debug('Telemetry poll frame:', err);
  }
}

/**
 * Updates all live UI elements to mirror backend terminal state in 1:1 real-time
 */
function updatePipelineTelemetryUI(data) {
  if (!data) return;

  const currentStep = data.current_step || 1;
  const stepName = data.step_name || 'Multi-Agent Pipeline';
  const stepEngine = data.step_engine || 'LangGraph';
  const message = data.message || 'Executing agent node...';
  const elapsed = (data.elapsed_seconds !== undefined && data.elapsed_seconds !== null)
    ? Number(data.elapsed_seconds).toFixed(1)
    : ((Date.now() - (pipelineStartTime || Date.now())) / 1000).toFixed(1);

  // 1. Update Loading Header
  const loadingTitle = document.getElementById('loadingTitle');
  const loadingSub = document.getElementById('loadingSubtitle');
  if (loadingTitle) loadingTitle.textContent = `Curating Edition: ${stepName}`;
  if (loadingSub) loadingSub.textContent = message;

  // 2. Update Live Stepper (1 to 5)
  const steps = ['stepAgent1', 'stepAgent2', 'stepAgent3', 'stepAgent4', 'stepAgent5'];
  steps.forEach((stepId, idx) => {
    const stepNum = idx + 1;
    const el = document.getElementById(stepId);
    const line = document.getElementById(`stepLine${stepNum}`);
    if (!el) return;

    if (data.status === 'completed' || stepNum < currentStep) {
      el.className = 'stepper-step complete';
      if (line) line.className = 'stepper-line complete';
    } else if (stepNum === currentStep) {
      el.className = 'stepper-step active';
      if (line) line.className = 'stepper-line active';
    } else {
      el.className = 'stepper-step';
      if (line) line.className = 'stepper-line';
    }
  });

  // 3. Update Active Agent Telemetry Card
  const telemetryStepBadge = document.getElementById('telemetryStepBadge');
  const telemetryEngineBadge = document.getElementById('telemetryEngineBadge');
  const telemetryTimer = document.getElementById('telemetryTimer');
  const telemetryAgentName = document.getElementById('telemetryAgentName');
  const telemetryAgentDesc = document.getElementById('telemetryAgentDesc');

  if (telemetryStepBadge) telemetryStepBadge.textContent = `AGENT ${currentStep} OF 5`;
  if (telemetryEngineBadge) telemetryEngineBadge.textContent = stepEngine;
  if (telemetryTimer) telemetryTimer.textContent = `Elapsed: ${elapsed}s`;
  if (telemetryAgentName) telemetryAgentName.textContent = stepName;
  if (telemetryAgentDesc) telemetryAgentDesc.textContent = message;

  // 4. Update Live Terminal Log Stream
  const terminalMirrorLogs = document.getElementById('terminalMirrorLogs');
  const terminalSyncIndicator = document.getElementById('terminalSyncIndicator');
  if (terminalSyncIndicator) {
    terminalSyncIndicator.textContent = data.status === 'running' ? 'LIVE SYNC ACTIVE' : (data.status === 'error' ? 'ERROR DETECTED' : 'CURATION COMPLETE');
    terminalSyncIndicator.style.color = data.status === 'error' ? '#F87171' : '#4ADE80';
  }

  if (terminalMirrorLogs && Array.isArray(data.logs) && data.logs.length > 0) {
    terminalMirrorLogs.innerHTML = data.logs.map(logLine => {
      const isErr = logLine.includes('ERROR') || logLine.includes('Exception') || logLine.includes('failed');
      const isHighlight = logLine.includes('retrieved') || logLine.includes('retained') || logLine.includes('distilled') || logLine.includes('produced') || logLine.includes('finished');
      const cls = isErr ? 'terminal-log-row err' : (isHighlight ? 'terminal-log-row highlight' : 'terminal-log-row');
      return `<div class="${cls}">${escapeHtml(logLine)}</div>`;
    }).join('');
    terminalMirrorLogs.scrollTop = terminalMirrorLogs.scrollHeight;
  }
}

/**
 * Renders prominent, high-visibility error alert box with simple plain-English explanations
 */
function renderPipelineError(errorObj, personaId) {
  stopPipelinePolling();
  showLoading(false);
  if (feedSection) feedSection.classList.add('hidden');
  if (!feedError) return;

  const errTitle = document.getElementById('errorTitle');
  const errMsg = document.getElementById('errorMessage');
  const errBadge = document.getElementById('errorTypeBadge');
  const errAgent = document.getElementById('errorAgentTag');
  const recoveryText = document.getElementById('errorRecoveryText');
  const terminalDetails = document.getElementById('errorTerminalDetails');
  const terminalCode = document.getElementById('errorTerminalCode');
  const retryBtn = document.getElementById('retryErrorBtn');
  const genBtnText = document.getElementById('generateNowBtnText');

  feedError.classList.remove('hidden');

  const failedAgent = errorObj?.failed_agent || errorObj?.step_name || 'Agent Pipeline';
  const failedEngine = errorObj?.failed_engine || errorObj?.step_engine || 'System';
  const title = errorObj?.error_title || 'Pipeline Execution Interrupted';
  const message = errorObj?.error_message || 'An unexpected error occurred during news curation.';
  const hint = errorObj?.recovery_hint || 'Verify your environment credentials and click Retry below.';
  const details = errorObj?.error_details || (typeof errorObj === 'string' ? errorObj : '');

  if (errBadge) errBadge.textContent = 'PIPELINE EXECUTION INTERRUPTED';
  if (errAgent) errAgent.textContent = `Failed at: ${failedAgent} (${failedEngine})`;
  if (errTitle) errTitle.textContent = title;
  if (errMsg) errMsg.textContent = message;
  if (recoveryText) recoveryText.textContent = hint;

  if (details && terminalCode && terminalDetails) {
    terminalCode.textContent = details;
    terminalDetails.classList.remove('hidden');
  } else if (terminalDetails) {
    terminalDetails.classList.add('hidden');
  }

  if (genBtnText) genBtnText.textContent = 'Retry Feed Refresh';
  if (retryBtn) {
    retryBtn.classList.remove('hidden');
    retryBtn.onclick = () => {
      feedError.classList.add('hidden');
      fetchWeeklyFeed(personaId || currentPersonaId);
    };
  }
}

/**
 * Triggers the pipeline via POST /feed/${personaId}/refresh with real-time terminal sync
 */
async function triggerFeedRefresh(personaId) {
  if (isRefreshing) return;
  isRefreshing = true;

  setRefreshButtonsLoading(true);
  hideError();
  showLoading(true, personaId);
  showToast(`Pipeline active for '${personaId}'... Synchronizing with terminal.`);

  // Start polling backend status immediately
  startPipelinePolling(personaId, (statusData) => {
    // Pipeline completed via background or stream
    fetchWeeklyFeed(personaId);
  });

  try {
    const response = await fetch(`${API_BASE_URL}/feed/${personaId}/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    const data = await response.json().catch(() => ({}));

    if (response.ok && data.status === 'success' && data.feed) {
      stopPipelinePolling();
      showLoading(false);
      renderFeedResults(data.feed);
      if (feedSection) feedSection.classList.remove('hidden');
      hideError();
      showToast(`Feed curated successfully for '${personaId}'!`);
    } else if (data.status === 'error' || !response.ok) {
      stopPipelinePolling();
      showLoading(false);
      const errPayload = data.pipeline_status?.error || {
        error_title: data.message || 'Pipeline Execution Error',
        error_message: 'The agent pipeline encountered an issue during execution.',
        recovery_hint: 'Review the terminal trace below or click Retry.',
        error_details: data.detail || data.message || JSON.stringify(data)
      };
      renderPipelineError(errPayload, personaId);
      showToast(`Pipeline execution halted: ${data.message || 'Error'}`);
    } else {
      // Running in background - keep polling until completion
      showToast('Pipeline actively running in background. Watching terminal progress...');
    }
  } catch (error) {
    console.error('Pipeline trigger error:', error);
    stopPipelinePolling();
    showLoading(false);
    renderPipelineError({
      error_title: 'Connection to Backend Failed',
      error_message: `Could not connect to API server at ${API_BASE_URL}: ${error.message}`,
      recovery_hint: 'Ensure the FastAPI backend process (run_project.bat) is running in the terminal.',
      error_details: error.stack || String(error)
    }, personaId);
  } finally {
    setRefreshButtonsLoading(false);
    isRefreshing = false;
  }
}

/**
 * Sets loading spinner on all refresh buttons
 */
function setRefreshButtonsLoading(loading) {
  const buttons = [mastheadRefreshBtn, heroRefreshBtn, generateNowBtn].filter(Boolean);
  buttons.forEach(btn => {
    btn.disabled = loading;
    const textSpan = btn.querySelector('.btn-refresh-text') || btn.querySelector('span:last-child');
    const svgIcon = btn.querySelector('svg');

    if (loading) {
      btn.classList.add('loading');
      if (svgIcon) svgIcon.classList.add('spin-animation');
      if (textSpan) textSpan.textContent = 'Generating...';
    } else {
      btn.classList.remove('loading');
      if (svgIcon) svgIcon.classList.remove('spin-animation');
      if (textSpan) {
        if (btn.id === 'generateNowBtn') {
          textSpan.textContent = 'Generate Feed Now';
        } else {
          textSpan.textContent = 'Refresh Feed';
        }
      }
    }
  });
}

/**
 * UI State Helpers
 */
function showLoading(isLoading, personaId = null) {
  if (!feedLoading) return;
  if (isLoading) {
    feedLoading.classList.remove('hidden');
    if (personaId) {
      startPipelinePolling(personaId);
    }
  } else {
    feedLoading.classList.add('hidden');
    stopPipelinePolling();
  }
}

function showError(title, message) {
  renderPipelineError({
    error_title: title,
    error_message: message,
    recovery_hint: 'Click Generate Feed Now below to trigger the multi-agent pipeline and assemble stories.'
  });
}

function hideError() {
  if (feedError) feedError.classList.add('hidden');
}

function showToast(message) {
  if (!toastContainer) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4500);
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const [year, month, day] = dateStr.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthName = months[parseInt(month, 10) - 1] || month;
  return `${monthName} ${day}`;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Initialize application on DOM ready
document.addEventListener('DOMContentLoaded', initApp);
