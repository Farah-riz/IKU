
const openButton = document.getElementById("open-btn");

openButton.addEventListener("click", () => {
  window.location.href = "login.html";
});

function switchUser() {
  localStorage.removeItem("demoUser");
  window.location.href = "login.html";
}
