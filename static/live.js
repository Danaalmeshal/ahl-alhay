// Keeps "active now" status fresh and marks notifications as read when the bell opens.
(function () {
  var meta = document.querySelector('meta[name="csrf-token"]');
  var token = meta ? meta.content : "";
  function post(url) {
    var body = new URLSearchParams({ _csrf: token });
    return fetch(url, { method: "POST", body: body, credentials: "same-origin",
                        headers: { "X-Requested-With": "fetch" } });
  }
  // Heartbeat: the member stays "active" while a page is open.
  setInterval(function () { if (!document.hidden) post("/ping"); }, 60000);

  var bell = document.getElementById("notif");
  if (bell) {
    bell.addEventListener("toggle", function () {
      var dot = document.getElementById("notif-dot");
      if (bell.open && dot) {
        post("/notifications/read").then(function () { dot.remove(); });
      }
    });
    document.addEventListener("click", function (e) {
      if (bell.open && !bell.contains(e.target)) bell.open = false;
    });
  }
})();
