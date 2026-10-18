
const openButton = document.getElementById("open-btn");

if (openButton) {
  openButton.addEventListener("click", () => {
    window.location.href = "/login";
  });
}

function switchUser() {
  fetch("/api/logout", {method: "POST"})
    .finally(() => {
      window.location.href = "/login";
    });
}
