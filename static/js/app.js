'use strict';
const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
const pronounce = (value) => {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const msg = new SpeechSynthesisUtterance(value);
  msg.lang = 'ja-JP'; msg.rate = .78;
  window.speechSynthesis.speak(msg);
};
document.querySelectorAll('.flip-card').forEach(card => {
  card.addEventListener('click', () => {
    const nowFlipped = card.classList.toggle('flipped');
    card.setAttribute('aria-pressed', String(nowFlipped));
    const jp = card.querySelector('.front strong')?.textContent;
    if (jp) pronounce(jp);
  });
});
function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}
async function openQuiz(button) {
  const {quizKind:kind, quizUnit:unit} = button.dataset;
  const root = document.getElementById('quiz-area');
  root.replaceChildren(el('p', '', 'Preparando preguntas…'));
  root.scrollIntoView({behavior:'smooth',block:'start'});
  const url = `/api/quiz/${encodeURIComponent(kind)}/${encodeURIComponent(unit)}`;
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('No se pudieron cargar las preguntas.');
    const data = await response.json();
    const shell = el('section','quiz-shell');
    shell.append(el('h2','','🌸 Mini evaluación'),el('p','','Elige una respuesta para cada pregunta. Tu intento se guardará al terminar.'));
    const form = el('form');
    data.questions.forEach((q,i) => {
      const fieldset = el('fieldset','question');
      const legend = el('legend','',`${i+1}. ¿Qué significa / cómo se lee «${q.prompt}»?`);
      fieldset.append(legend);
      q.choices.forEach(choice => {
        const label = el('label');
        const radio = document.createElement('input');
        radio.type='radio'; radio.name=`q${i}`; radio.value=choice; radio.required=true;
        label.append(radio,document.createTextNode(choice));
        fieldset.append(label);
      });
      form.append(fieldset);
    });
    const submit = el('button','button primary','Calificar y guardar mi resultado ⭐');
    submit.type='submit';
    form.append(submit);
    shell.append(form); root.replaceChildren(shell);
    form.addEventListener('submit',async event => {
      event.preventDefault();
      const answers = data.questions.map((_,i) => new FormData(form).get(`q${i}`));
      if(answers.some(x=>x===null)){alert('Responde todas las preguntas.');return;}
      submit.disabled=true;submit.textContent='Guardando…';
      try {
        const reply=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({answers})});
        const result=await reply.json();
        if(!reply.ok) throw new Error(result.error || 'Error al guardar.');
        const box=el('div','results');
        box.append(el('h2','',`${result.passed?'🎉 ¡Muy bien!':'🌱 Sigue practicando'} — ${result.score}/${result.total}`),
          el('p','',result.passed?'¡Superaste el 80%! Tu progreso quedó registrado.':'Necesitas 80% para marcar esta unidad como lograda. Puedes repetirla.'));
        const list=el('ul');
        result.detail.forEach(x=>{
          const li=el('li',x.is_correct?'':'wrong',`${x.is_correct?'✓':'✗'} ${x.prompt}: ${x.chosen}${x.is_correct?'':` (respuesta: ${x.correct})`}`);
          list.append(li);
        });
        box.append(list);
        form.replaceWith(box);
        const retry=el('button','button secondary','Repetir evaluación ↻');
        retry.addEventListener('click',()=>openQuiz(button));
        shell.append(retry);
        const note=el('p','', 'El historial completo está disponible en Mi progreso.');
        shell.append(note);
      } catch(error) {alert(error.message);submit.disabled=false;submit.textContent='Volver a intentar';}
    });
  } catch(error) {root.replaceChildren(el('p','notice',error.message));}
}
document.querySelectorAll('[data-quiz-kind]').forEach(button=>button.addEventListener('click',()=>openQuiz(button)));
