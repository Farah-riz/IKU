
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOURS = [9, 10, 11, 12, 13, 14, 15, 16];
const START_MONDAY = new Date(2026, 9, 19);

const defaultFree = [
  "Mon-10", "Mon-11", "Tue-14", "Tue-15",
  "Wed-11", "Thu-15", "Fri-10", "Sat-13", "Sat-14"
];

const people = [
  {
    id: "farah",
    name: "You (Farah)",
    source: "My calendar",
    color: "#e3aa96",
    free: [...defaultFree]
  },
  {
    id: "liz",
    name: "Liz",
    source: "Demo calendar",
    color: "#e2c7aa",
    free: [
      "Mon-10", "Mon-11", "Tue-14",
      "Wed-11", "Thu-15", "Sat-13"
    ]
  },
  {
    id: "freya",
    name: "Freya",
    source: "Demo calendar",
    color: "#aec9c4",
    free: [
      "Mon-10", "Tue-14", "Wed-11",
      "Fri-10", "Sat-13"
    ]
  },
  {
    id: "anjika",
    name: "Anjika",
    source: "Demo calendar",
    color: "#cbd5ee",
    free: [
      "Mon-10", "Tue-15", "Thu-15",
      "Fri-12", "Sat-13"
    ]
  }
];

const savedSuggestions = [
  {
    name: "Seven Sisters hike",
    detail: "A coastal day out",
    day: null
  },
  {
    name: "IKU Celebratory Brunch",
    detail: "celebrate winning the IKU Hackathon with a brunch at Frankie and Benny's",
    day: "Mon"
  },
  {
    name: "Free arts and crafts afternoon in Camden",
    detail: "Saturday 24th · afternoon",
    day: "Sat",
    minHour: 12
  }
];

const selected = new Set(["farah", "liz"]);

let weekOffset = 0;
let currentMatch = null;
let chosenSuggestion = null;

const friendList = document.getElementById("friendList");
const grid = document.getElementById("calendarGrid");
const resultList = document.getElementById("resultList");
const matchCount = document.getElementById("matchCount");
const resultNote = document.getElementById("resultNote");
const modal = document.getElementById("planModal");
const placeInput = document.getElementById("placeInput");

// DATE HELPERS

function formatHour(hour) {
  const suffix = hour >= 12 ? "pm" : "am";
  return `${hour % 12 || 12}${suffix}`;
}

function getMonday() {
  const monday = new Date(START_MONDAY);
  monday.setDate(monday.getDate() + weekOffset * 7);
  return monday;
}

function getDate(day) {
  const date = getMonday();
  date.setDate(date.getDate() + DAYS.indexOf(day));
  return date;
}

function dateLabel(day) {
  return getDate(day).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric"
  });
}

function activePeople() {
  return people.filter(
    p => p.id === "alex" || selected.has(p.id)
  );
}

function storageKey() {
  return `reelplans-free-${weekOffset}`;
}

function loadAvailability() {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey()));
    people[0].free = Array.isArray(stored)
      ? stored
      : [...defaultFree];
  } catch {
    people[0].free = [...defaultFree];
  }
}

function isFree(person, slot) {
  return person.free.includes(slot);
}

// FRIEND TOGGLES

function renderFriends() {
  friendList.innerHTML = "";

  people.forEach((person, index) => {
    const row = document.createElement("label");
    row.className = "friend";

    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.style.background = person.color;
    avatar.textContent = index === 0 ? "A" : person.name[0];

    const info = document.createElement("span");
    info.className = "friend-info";

    const name = document.createElement("strong");
    name.textContent = person.name;

    const source = document.createElement("small");
    source.textContent = person.source;

    info.append(name, source);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = index === 0 || selected.has(person.id);
    checkbox.disabled = index === 0;

    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        selected.add(person.id);
      } else {
        selected.delete(person.id);
      }

      renderCalendar();
    });

    row.append(avatar, info, checkbox);
    friendList.appendChild(row);
  });
}

// AVAILABILITY MATCHING

function getMatches() {
  const matches = [];
  const active = activePeople();

  DAYS.forEach(day => {
    HOURS.forEach(hour => {
      const slot = `${day}-${hour}`;

      if (active.every(p => isFree(p, slot))) {
        matches.push({ day, hour, slot });
      }
    });
  });

  return matches;
}

// CLICK TO BLOCK / UNBLOCK

function toggleSlot(slot) {
  const free = people[0].free;
  const index = free.indexOf(slot);

  if (index === -1) {
    free.push(slot);
  } else {
    free.splice(index, 1);
  }

  localStorage.setItem(
    storageKey(),
    JSON.stringify(free)
  );

  document.getElementById("pushBtn").disabled = false;
  document.getElementById("pushHint").textContent =
    "Your availability changed. Share it with your friends.";

  renderCalendar();
}

// CALENDAR GRID

function renderCalendar() {
  const matches = getMatches();
  const matchKeys = new Set(matches.map(m => m.slot));

  grid.innerHTML = "";

  const corner = document.createElement("div");
  corner.className = "grid-head";
  grid.appendChild(corner);

  DAYS.forEach(day => {
    const head = document.createElement("div");
    head.className = "grid-head";

    const title = document.createElement("strong");
    title.textContent = day;

    const date = document.createElement("small");
    date.textContent = getDate(day).getDate();

    head.append(title, date);
    grid.appendChild(head);
  });

  HOURS.forEach(hour => {
    const label = document.createElement("div");
    label.className = "time-label";
    label.textContent = formatHour(hour);
    grid.appendChild(label);

    DAYS.forEach(day => {
      const slot = `${day}-${hour}`;
      const ownFree = isFree(people[0], slot);
      const everyoneFree = matchKeys.has(slot);

      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "slot";

      if (ownFree) {
        cell.classList.add("own-free");
      }

      if (everyoneFree && activePeople().length > 1) {
        cell.classList.add("match");
      }

      cell.textContent = !ownFree
        ? "Busy"
        : everyoneFree && activePeople().length > 1
          ? "All free!"
          : "Free";

      cell.title =
        `Toggle availability: ${dateLabel(day)} at ${formatHour(hour)}`;

      cell.setAttribute("aria-pressed", String(!ownFree));

      cell.addEventListener("click", () => toggleSlot(slot));

      grid.appendChild(cell);
    });
  });

  renderResults(matches);
}

// MATCHING TIMES

function renderResults(matches) {
  matchCount.textContent =
    `${matches.length} ${matches.length === 1 ? "match" : "matches"}`;

  resultList.innerHTML = "";

  if (matches.length === 0) {
    resultList.textContent =
      "No shared free slots. Try another hour or change which friends are selected.";
  }

  matches.forEach(match => {
    const card = document.createElement("button");
    card.className = "result";

    const title = document.createElement("strong");
    title.textContent =
      `${match.day} ${getDate(match.day).getDate()} · ${formatHour(match.hour)}`;

    const detail = document.createElement("small");
    detail.textContent =
      `${formatHour(match.hour)} – ${formatHour(match.hour + 1)} · Everyone free`;

    card.append(title, detail);

    card.addEventListener("click", () => openPlan(match));

    resultList.appendChild(card);
  });

  resultNote.textContent =
    `Comparing ${activePeople().map(p => p.name).join(", ")}. Friend schedules are demo data.`;
}

// POPUP

function openPlan(match) {
  currentMatch = match;
  chosenSuggestion = null;

  document.getElementById("modalDate").textContent =
    `${dateLabel(match.day)} · ${formatHour(match.hour)} – ${formatHour(match.hour + 1)}`;

  placeInput.value = "";
  document.getElementById("modalMessage").textContent = "";

  renderSuggestions();
  modal.hidden = false;
  document.getElementById("closeModal").focus();
}

function renderSuggestions() {
  const container = document.getElementById("suggestions");
  container.innerHTML = "";

  savedSuggestions.forEach(suggestion => {
    const button = document.createElement("button");
    button.className = "suggestion";

    const isFirstWeek = weekOffset === 0;

    const validDay =
      !suggestion.day ||
      suggestion.day === currentMatch.day;

    const validHour =
      !suggestion.minHour ||
      currentMatch.hour >= suggestion.minHour;

    const dateRestricted = suggestion.day !== null;

    const compatible =
      validDay &&
      validHour &&
      (!dateRestricted || isFirstWeek);

    const title = document.createElement("strong");
    title.textContent = suggestion.name;

    const detail = document.createElement("small");
    detail.textContent = compatible
      ? suggestion.detail
      : `${suggestion.detail} · Not for this time`;

    button.append(title, detail);

    if (!compatible) {
      button.disabled = true;
    }

    if (chosenSuggestion === suggestion.name) {
      button.classList.add("selected");
    }

    button.addEventListener("click", () => {
      chosenSuggestion = suggestion.name;
      placeInput.value = suggestion.name;
      renderSuggestions();
    });

    container.appendChild(button);
  });
}

function closeModal() {
  modal.hidden = true;
  currentMatch = null;
}

document.getElementById("closeModal")
  .addEventListener("click", closeModal);

modal.addEventListener("click", event => {
  if (event.target === modal) {
    closeModal();
  }
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !modal.hidden) {
    closeModal();
  }
});

// SAVE CONFIRMED PLANS

function getSavedPlans() {
  try {
    const plans = JSON.parse(
      localStorage.getItem("reelplans-plans")
    );
    return Array.isArray(plans) ? plans : [];
  } catch {
    return [];
  }
}

function renderSavedPlans() {
  const list = document.getElementById("savedPlans");
  list.innerHTML = "";

  const plans = getSavedPlans();

  if (!plans.length) {
    const item = document.createElement("li");
    item.textContent = "No plans confirmed yet.";
    list.appendChild(item);
    return;
  }

  plans.forEach(plan => {
    const item = document.createElement("li");
    item.textContent =
      `${plan.place} · ${plan.date} at ${formatHour(plan.hour)}`;
    list.appendChild(item);
  });
}

document.getElementById("confirmPlan")
  .addEventListener("click", () => {
    if (!currentMatch) return;

    const place = placeInput.value.trim();

    if (!place) {
      document.getElementById("modalMessage").textContent =
        "Choose a suggestion or enter a place first.";
      return;
    }

    const plans = getSavedPlans();

    plans.push({
      place,
      date: dateLabel(currentMatch.day),
      hour: currentMatch.hour,
      friends: activePeople().map(p => p.name)
    });

    localStorage.setItem(
      "reelplans-plans",
      JSON.stringify(plans)
    );

    renderSavedPlans();
    closeModal();
  });

// PUSH AVAILABILITY TO FRIENDS

async function pushToFriends() {
 function pushToFriends() {
  alert("Done! Your availability has been shared with your friends ♡");
 }
}
document.getElementById("pushBtn")
  .addEventListener("click", pushToFriends);

  
// WEEK NAVIGATION

function updateWeek() {
  const monday = getMonday();
  const saturday = getDate("Sat");

  const options = {
    day: "numeric",
    month: "short"
  };

  document.getElementById("weekTitle").textContent =
    `${monday.toLocaleDateString("en-GB", options)} – ${saturday.toLocaleDateString("en-GB", options)}`;

  loadAvailability();

  document.getElementById("pushBtn").disabled = true;
  document.getElementById("pushHint").textContent =
    "Change a time slot to share your updated availability.";

  renderCalendar();
}

document.getElementById("prevWeek")
  .addEventListener("click", () => {
    weekOffset--;
    updateWeek();
  });

document.getElementById("nextWeek")
  .addEventListener("click", () => {
    weekOffset++;
    updateWeek();
  });

// START APP

renderFriends();
renderSavedPlans();
updateWeek();
