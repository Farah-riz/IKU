
// Redirect existing demo users straight to the hub
const existingUser = localStorage.getItem("demoUser");

if (existingUser) {
  window.location.replace("calendar.html");
}

// One-click demo login
document.querySelectorAll(".user-card").forEach((button) => {
  button.addEventListener("click", () => {
    const userId = button.dataset.user;

    const demoUsers = {
      alex: {
        id: "alex",
        name: "Alex",
        avatar: "A"
      },
      sam: {
        id: "sam",
        name: "Sam",
        avatar: "S"
      }
    };

    const selectedUser = demoUsers[userId];

    if (!selectedUser) return;

    localStorage.setItem("demoUser", JSON.stringify(selectedUser));

    window.location.href = "calendar.html";
  });
});


