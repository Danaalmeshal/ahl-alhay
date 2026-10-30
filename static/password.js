// PBI 4A: live password-strength indicator (labels come from the page language).
(function () {
  var input = document.getElementById("password");
  if (!input) return;
  var fill = document.getElementById("strength-fill");
  var label = document.getElementById("strength-label");
  var rules = document.querySelectorAll("#pw-rules li");
  var box = document.querySelector(".strength");
  var d = box ? box.dataset : {};
  var names = ["", d.l1 || "ضعيفة", d.l2 || "قوية", d.l3 || "قوية جداً"];
  var title = d.title || "قوة كلمة المرور:";

  function check(pw) {
    var letters = (pw.match(/\p{L}/gu) || []).length;
    var digits = (pw.match(/\p{Nd}/gu) || []).length;
    var symbols = (pw.match(/[^\p{L}\p{Nd}\s]/gu) || []).length;
    return { letters: letters >= 4, digits: digits >= 3, symbol: symbols >= 1,
             mixedCase: /[a-z]/.test(pw) && /[A-Z]/.test(pw), long: pw.length >= 10 };
  }

  input.addEventListener("input", function () {
    var pw = input.value, r = check(pw);
    rules.forEach(function (li) { li.classList.toggle("ok", r[li.dataset.rule]); });
    var meetsRule = r.letters && r.digits && r.symbol;
    var level = !pw ? 0 : !meetsRule ? 1 : (r.long && r.mixedCase) ? 3 : 2;
    var text = names[level];
    fill.style.width = (level / 3 * 100) + "%";
    fill.className = "lvl-" + level;
    label.textContent = text ? title + " " + text : "";
  });
})();
