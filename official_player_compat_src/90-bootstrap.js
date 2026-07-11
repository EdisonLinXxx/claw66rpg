  function install() {
    return installRegisteredCompatPatches();
  }

  install();
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    install();
    if (tries >= 120) clearInterval(timer);
  }, 100);
