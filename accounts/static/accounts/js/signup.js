function selectPosition(el, value) {
  const buttons = el.parentElement.querySelectorAll('.auth-position-btn');
  buttons.forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('positionInput').value = value;
}

function validatePosition() {
  const v = document.getElementById('positionInput').value;
  if (!v) {
    alert('직급을 선택해주세요.');
    return false;
  }
  return true;
}
