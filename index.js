
const loginModal = document.getElementById("login-modal");
const loginForm = document.getElementById("login-form");
const nameInput = document.getElementById("user-name");

// Open login modal
function openLogin() {
  loginModal.classList.remove("hidden");
  nameInput.focus();
}

// Close login modal
function closeLogin() {
  loginModal.classList.add("hidden");
}

// Start planning
function startPlanning() {
  const savedName = localStorage.getItem("username");

  if (savedName) {
    goToBoard();
  } else {
    openLogin();
  }
}

// Placeholder for the next page
function goToBoard() {
  window.location.href = "board.html";
}

// Buttons
document.getElementById("login-btn")
  .addEventListener("click", openLogin);

document.getElementById("nav-start-btn")
  .addEventListener("click", startPlanning);

document.getElementById("hero-start-btn")
  .addEventListener("click", startPlanning);

document.getElementById("bottom-start-btn")
  .addEventListener("click", startPlanning);

document.getElementById("close-modal")
  .addEventListener("click", closeLogin);

// Close when clicking outside modal
loginModal.addEventListener("click", (event) => {
  if (event.target === loginModal) {
    closeLogin();
  }
});

// Close with Escape
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLogin();
  }
});

// Demo login
loginForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const username = nameInput.value.trim();

  if (!username) return;

  localStorage.setItem("username", username);

  closeLogin();
  goToBoard();
});
