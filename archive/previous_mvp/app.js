const intervalsDays = [1, 2, 4, 8, 16, 32];
const newVocabPool = [
  'comer',
  'viajar',
  'trabajar',
  'feliz',
  'cena',
  'amigo',
  'tiempo',
  'libro',
  'mujer',
  'raro',
  'dinero',
  'música',
  'sonrisa',
  'fiesta',
  'camino',
  'aire',
  'calle',
  'oficina',
  'niño',
  'familia'
];
const newPhrasePool = [
  '¿Qué tal?',
  'Hace buen día',
  'Estoy aprendiendo español',
  '¿Puedes repetirlo?',
  'Me alegra verte',
  '¿Qué hiciste hoy?',
  'Hablemos de lo que te gusta'
];
const grammarPool = [
  'Present progressive (Estoy + gerund)',
  'Simple past verbs with ser/ir',
  'Gender agreement with adjectives',
  'Use of “tú” vs “usted”',
  'Verb + infinitive after “quiero”',
  'Negation with no + verb'
];

const state = {
  profile: loadProfile(),
  logs: [],
  contentIndexes: {
    vocab: 0,
    phrases: 0,
    grammar: 0
  },
  struggleStreak: 0
};
const SIMPLIFY_TIERS = ['combined', 'short', 'word_check', 'gloss'];
let currentTierIndex = 0;
let lastFocusWord = '';

const onboardingPanel = document.getElementById('onboardingPanel');
const onboardingForm = document.getElementById('onboardingForm');
const sessionSummary = document.getElementById('sessionSummary');
const chatHistory = document.getElementById('chatHistory');
const messageForm = document.getElementById('messageForm');
const messageInput = messageForm.querySelector('textarea');
const inlineHint = document.getElementById('inlineHint');
const hintText = document.getElementById('hintText');
const logEntries = document.getElementById('logEntries');
const logsPanel = document.getElementById('logsPanel');
const toggleLogsBtn = document.getElementById('toggleLogs');

if (state.profile.meta?.goal) {
  onboardingPanel?.remove();
  sessionSummary.textContent = `Resuming topic: ${state.profile.meta.topic}`;
}

onboardingForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(onboardingForm);
  state.profile.meta = {
    goal: formData.get('goal'),
    topic: formData.get('topic') || 'everyday life',
    time: formData.get('time'),
    level: formData.get('level')
  };
  state.profile.meta.dailyPlan = state.profile.meta.dailyPlan || {};
  saveProfile(state.profile);
  onboardingPanel.remove();
  sessionSummary.textContent = `Starting with topic: ${state.profile.meta.topic}`;
});

toggleLogsBtn.addEventListener('click', () => {
  logsPanel.classList.toggle('expanded');
  toggleLogsBtn.textContent = logsPanel.classList.contains('expanded') ? 'Hide' : 'Show';
});

messageForm.addEventListener('submit', (event) => {
  event.preventDefault();
  handleMessageSubmit();
});

messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleMessageSubmit();
  }
});

async function handleMessageSubmit() {
  const value = messageInput.value.trim();
  if (!value) return;
  addBubble(value, 'user');
  messageInput.value = '';
  const { reviewSet, newItems } = computeScheduler(state.profile);
  const confusionSignal = detectConfusion(value);
  if (confusionSignal) {
    state.struggleStreak = Math.min(state.struggleStreak + 1, 3);
    nextSimplifyTier();
  } else if (state.struggleStreak > 0) {
    state.struggleStreak = Math.max(state.struggleStreak - 1, 0);
    if (state.struggleStreak === 0) {
      resetSimplifyTier();
    }
  }
  const promptPayload = {
    topic: state.profile.meta?.topic || 'everyday life',
    goals: state.profile.meta?.goal || 'develop conversational fluency',
    reviewSet,
    newItems,
    userMessage: value,
    signalConfusion: confusionSignal,
    simplifyTier: SIMPLIFY_TIERS[currentTierIndex],
    focusWord: lastFocusWord
  };
  const response = await callModel(promptPayload);
  addBubble(response.Nextt, 'agent');
  if (response.Correction) {
    state.struggleStreak = Math.min(state.struggleStreak + 1, 3);
    inlineHint.hidden = false;
    hintText.textContent = `${response.Correction} — ${response.Rationale}`;
    logNeedsWork(response, value);
    if (response.focusConcept) {
      resetConceptSpacing(response.focusConcept);
    }
    if (response.focusWord) {
      lastFocusWord = response.focusWord;
    }
    if (response.simplifyTier && SIMPLIFY_TIERS.includes(response.simplifyTier)) {
      currentTierIndex = SIMPLIFY_TIERS.indexOf(response.simplifyTier);
    }
  } else {
    inlineHint.hidden = true;
    if (state.struggleStreak > 0) {
      state.struggleStreak -= 1;
    }
    if (response.understoodWord) {
      resetSimplifyTier();
    }
  }
  updateProfileExposure(reviewSet);
  state.logs.push({
    type: 'turn',
    timestamp: Date.now(),
    prompt: promptPayload,
    response
  });
  renderLogs();
}

function loadProfile() {
  const raw = localStorage.getItem('learnerProfile');
  if (!raw) {
    return {
      concepts: [],
      meta: {}
    };
  }
  try {
    const profile = JSON.parse(raw);
    profile.meta = profile.meta || {};
    profile.meta.dailyPlan = profile.meta.dailyPlan || { day: null };
    profile.concepts = profile.concepts || [];
    return profile;
  } catch (err) {
    console.error('Failed to parse profile');
    return {
      concepts: [],
      meta: {}
    };
  }
}

function saveProfile(profile) {
  // AUDIT: localStorage has limited quota — if the profile grows unbounded we may need to archive older review history.
  localStorage.setItem('learnerProfile', JSON.stringify(profile));
}

function computeScheduler(profile) {
  const today = getDayNumber();
  const reviewSet = profile.concepts.filter((concept) => {
    const interval = intervalsDays[concept.intervalIndex] || intervalsDays[intervalsDays.length - 1];
    return today - concept.lastReviewed >= interval;
  });
  const plan = profile.meta.dailyPlan || { day: null };
  let newItems;
  if (plan.day === today && plan.items) {
    newItems = plan.items;
  } else {
    newItems = {
      vocab: sliceNextItems(newVocabPool, state.contentIndexes, 'vocab', 12),
      phrases: sliceNextItems(newPhrasePool, state.contentIndexes, 'phrases', 5),
      grammar: sliceNextItems(grammarPool, state.contentIndexes, 'grammar', 1)
    };
    profile.meta.dailyPlan = {
      day: today,
      items: newItems
    };
    registerNewConcepts(newItems, profile.meta.topic || 'everyday life');
    saveProfile(profile);
  }
  return { reviewSet, newItems };
}

function sliceNextItems(pool, indexes, key, amount) {
  const pointer = indexes[key] % pool.length;
  const slice = [];
  for (let i = 0; i < amount; i += 1) {
    slice.push(pool[(pointer + i) % pool.length]);
  }
  indexes[key] = (pointer + amount) % pool.length;
  return slice;
}

function registerNewConcepts(newItems, topic) {
  const today = getDayNumber();
  Object.entries(newItems).forEach(([type, entries]) => {
    entries.forEach((text) => {
      if (!state.profile.concepts.find((concept) => concept.text === text && concept.type === type)) {
        state.profile.concepts.push({
          text,
          type,
          topic,
          exposures: 0,
          lastReviewed: today,
          intervalIndex: 0
        });
      }
    });
  });
  // AUDIT: New concepts persist indefinitely — if the list grows too fast we may need pruning or archiving logic.
  saveProfile(state.profile);
}

function updateProfileExposure(reviewSet) {
  const today = getDayNumber();
  reviewSet.forEach((concept) => {
    concept.exposures += 1;
    concept.lastReviewed = today;
    if (concept.intervalIndex < intervalsDays.length - 1) {
      concept.intervalIndex += 1;
    }
  });
  // AUDIT: If reviews fire too often, the exposure count will spike — consider throttling to avoid hitting localStorage limits.
  saveProfile(state.profile);
}

function resetConceptSpacing(text) {
  const concept = state.profile.concepts.find((item) => item.text === text);
  if (!concept) return;
  concept.intervalIndex = 0;
  concept.lastReviewed = getDayNumber();
  saveProfile(state.profile);
}

function logNeedsWork(response, message) {
  const entry = {
    type: 'needs_work',
    timestamp: Date.now(),
    message,
    correction: response.Correction,
    rationale: response.Rationale
  };
  state.logs.push(entry);
}

function renderLogs() {
  logEntries.innerHTML = '';
  state.logs.slice(-25).reverse().forEach((log) => {
    const card = document.createElement('div');
    card.className = 'log-card';
    if (log.type === 'needs_work') {
      card.innerHTML = `<strong>${new Date(log.timestamp).toLocaleTimeString()} • Needs work</strong>
        <p>${log.message}</p>
        <p><em>${log.correction}</em></p>`;
    } else {
      card.innerHTML = `<strong>${new Date(log.timestamp).toLocaleTimeString()} • Prompt</strong>
        <p>${log.prompt.userMessage}</p>
        <p><small>${log.prompt.topic} • ${log.prompt.goals}</small></p>`;
    }
    logEntries.appendChild(card);
  });
}

function addBubble(text, side) {
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${side}`;
  bubble.textContent = text;
  chatHistory.appendChild(bubble);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function getDayNumber() {
  return Math.floor(Date.now() / 86400000);
}

const PROMPT_INSTRUCTIONS = `
You will be given a current topic, the learner's goals, a set of review items, new items, and struggle items along with the user's latest message.
If it is the first turn you will get an onboarding summary.
Evaluate the user's response and, if anything is not correct for conversational fluency, report the rationale so we can display it inline and store the "needs work" note.
Keep the conversation flowing, revisit scheduled review items, and introduce the new concepts in the same turn.
If the user is struggling or signals confusion, especially after repeated corrections, respond with simpler vocabulary, shorter sentences, and an easier follow-up question—just like a patient native speaker would help.
Always return structured JSON with the schema: { "Correction": "...", "Rationale": "...", "Nextt": "..." }.
`;

function buildPrompt(payload) {
  const reviewList = payload.reviewSet
    .map((concept) => `- ${concept.text} (${concept.type}) last seen ${concept.lastReviewed}`)
    .join('\n');
  const newList = [
    ...payload.newItems.vocab.map((item) => `Vocab: ${item}`),
    ...payload.newItems.phrases.map((item) => `Phrase: ${item}`),
    ...payload.newItems.grammar.map((item) => `Grammar: ${item}`)
  ].join('\n');
  const toneHint =
    payload.signalConfusion || state.struggleStreak > 1
      ? 'Simplify language, keep sentences short, and double-check understanding.'
      : 'Keep the flow natural but focused on practice.';
  return `
${PROMPT_INSTRUCTIONS}
Current topic: ${payload.topic}
Learner goals: ${payload.goals}
Signal confusion?: ${payload.signalConfusion ? 'yes' : 'no'}
Review items:
${reviewList || '- none yet'}
New concepts:
${newList}
Latest user message:
${payload.userMessage}
Tone hint: ${toneHint}
`;
}

function detectConfusion(message) {
  const normalized = message.toLowerCase();
  const triggers = [
    "i don't understand",
    "no entiendo",
    "what should i say",
    "can you help",
    "help me",
    "still confused",
    "lost",
    "i'm stuck",
    "i am not sure",
    "i'm not sure"
  ];
  return triggers.some((trigger) => normalized.includes(trigger));
}

function nextSimplifyTier() {
  if (currentTierIndex < SIMPLIFY_TIERS.length - 1) {
    currentTierIndex += 1;
  }
}

function resetSimplifyTier() {
  currentTierIndex = 0;
  lastFocusWord = '';
}

async function callModel(payload) {
  const promptText = buildPrompt(payload);
  const openAiKey =
    window.OPENAI_API_KEY || window.OPENAI_KEY || window?.ENV?.OPENAI_API_KEY || null;
  if (openAiKey) {
    try {
      const response = await fetch('https://api.openai.com/v1/responses', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${openAiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          input: promptText
        })
      });
      const data = await response.json();
      const textChunk = Array.isArray(data.output)
        ? data.output
            .map((item) => {
              if (item.content) {
                return item.content.map((block) => block.text || block).join('');
              }
              return '';
            })
            .join(' ')
        : '';
      const parsed = parseStructuredOutput(textChunk);
      if (parsed) {
        return parsed;
      }
    } catch (err) {
      console.error('LLM call failed, falling back to stub:', err);
    }
  }
  return stubResponse(payload, promptText);
}

function parseStructuredOutput(rawText) {
  const trimmed = rawText.trim();
  const jsonMatch = trimmed.match(/\{[\s\S]*\}/);
  if (!jsonMatch) return null;
  try {
    return JSON.parse(jsonMatch[0]);
  } catch (err) {
    console.error('Failed to parse model output JSON', err);
    return null;
  }
}

function stubResponse(payload, promptText) {
  const reviewCandidate = payload.reviewSet[0];
  const conceptText = reviewCandidate?.text || payload.newItems.vocab[0] || 'algo nuevo';
  const tier = SIMPLIFY_TIERS[currentTierIndex] || 'combined';
  let correction = reviewCandidate
    ? `Try saying "${reviewCandidate.text}" with ${reviewCandidate.type} in mind.`
    : '';
  let rationale = reviewCandidate
    ? `Reviewing ${reviewCandidate.text} keeps the ${reviewCandidate.type} strong.`
    : '';
  let next = '';
  let focusWord = reviewCandidate?.text || conceptText;
  let understoodWord = false;
  switch (tier) {
    case 'short':
      next = `¿Puedes decir una frase corta sobre ${conceptText}?`;
      break;
    case 'word_check':
      correction = '';
      rationale = '';
      next = `¿Sabes qué significa "${focusWord}"?`;
      break;
    case 'gloss':
      correction = '';
      rationale = '';
      next = `"[${focusWord}]" significa "${translateWord(focusWord)}". Úsalo en una frase corta.`;
      break;
    default:
      next = `Excelente—cuéntame sobre ${conceptText} y usa ${payload.newItems.grammar[0] || 'un nuevo punto gramatical'} si puedes.`;
  }
  if (tier === 'gloss') {
    understoodWord = true;
    resetSimplifyTier();
  }
  return {
    Correction: correction,
    Rationale: rationale,
    Nextt: next,
    focusConcept: reviewCandidate?.text,
    focusWord,
    simplifyTier: tier,
    understoodWord
  };
}

function translateWord(word) {
  const dictionary = {
    comer: 'to eat',
    viajar: 'to travel',
    trabajar: 'to work',
    feliz: 'happy',
    cena: 'dinner'
  };
  // AUDIT: Translation dictionary is minimal and static; expand or hook to a real glossary before going live.
  return dictionary[word.toLowerCase()] || 'something important';
}
