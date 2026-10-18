
async function redirectIfLoggedIn() {
  const response = await fetch("/api/session");
  const body = await response.json();
  if (body.user) window.location.replace("/add-event");
}

redirectIfLoggedIn().catch(() => {});

document.querySelectorAll(".user-card").forEach((button) => {
  button.addEventListener("click", async () => {
    const userId = button.dataset.user;
    button.disabled = true;
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({user_id: userId})
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not log in.");
      window.location.href = "/add-event";
    } catch (error) {
      button.disabled = false;
      window.alert(error.message);
    }
  });
});


