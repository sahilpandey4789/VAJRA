export function toast(message, type = "default", duration = 3000) {
  const host = document.getElementById("toastHost");
  const el = document.createElement("div");
  el.className = `toast ${type === "default" ? "" : type}`.trim();
  el.textContent = message;
  el.setAttribute("role", "status");
  host.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 260);
  }, duration);
}
