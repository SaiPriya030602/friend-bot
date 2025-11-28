const promptInput = document.getElementById('prompt');
const generateButton = document.getElementById('generate');
const poemOutput = document.getElementById('poem');

generateButton.addEventListener('click', async () => {
  const prompt = promptInput.value;

  try {
    const response = await fetch('/generate_poem/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt })
    });

    const data = await response.json();
    poemOutput.textContent = data.poem;
  } catch (error) {
    console.error('Error:', error);
    poemOutput.textContent = 'Error generating poem.';
  }
});