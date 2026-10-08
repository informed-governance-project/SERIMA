// The download link deletes the export job server-side, so this results page goes stale as
// soon as it is used. Move the user on to the admin index once the download has started.
document.addEventListener("DOMContentLoaded", function () {
  const link = document.getElementById("data_file");
  if (!link) {
    return;
  }
  link.addEventListener("click", function () {
    setTimeout(function () {
      window.location = link.dataset.redirectUrl;
    }, 2000);
  });
});
