import { surveyRecords, surveyVariables, weightedRanking, weightedVoteRows } from "./survey.js";

const SURVEY_URL = "https://docs.google.com/spreadsheets/d/13p58SpkkGQqmZIS4VREej0Kqhi14y8rQmCkzGmx40QU/gviz/tq?tqx=out:csv&gid=1975671607";
const target = document.querySelector("#live-survey");
const voteFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const percentFormat = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });
const currentDriverNames = [
  "Lando Norris", "Oscar Piastri", "Charles Leclerc", "Carlos Sainz", "George Russell",
  "Kimi Antonelli", "Pierre Gasly", "Esteban Ocon", "Yuki Tsunoda", "Liam Lawson",
  "Alexander Albon", "Lance Stroll", "Nico Hulkenberg", "Gabriel Bortoleto",
  "Oliver Bearman", "Isack Hadjar", "Franco Colapinto", "Jack Doohan"
];
const variableLabels = {
  country: "Country", gender: "Gender", age: "Age", follows: "Follows F1",
  discovery: "How they found F1", years: "Time as a fan", media: "Media used",
  otherSeries: "Other series", criteria: "GOAT criterion", carWeight: "Car vs. driver weight",
  fairness: "Are title comparisons unfair?", statistics: "Weight given to statistics"
};
const englishValues = new Map([
  ["Femenino", "Female"], ["Masculino", "Male"], ["Sí", "Yes"], ["Esporádicamente", "Occasionally"],
  ["No sigue / solo redes", "Does not follow / social media only"], ["Empezó este año", "Started this year"],
  ["El año pasado", "Last year"], ["2 a 4 años", "2 to 4 years"], ["5 años o más", "5 years or more"],
  ["Redes sociales / memes", "Social media / memes"], ["Piloto de su país", "A driver from their country"],
  ["Tradición familiar / amigos", "Family tradition / friends"], ["Siempre siguió el automovilismo", "Always followed motorsport"],
  ["Ninguna", "None"], ["Otras ocasionalmente", "Other series occasionally"],
  ["Resultados", "Results"], ["Talento más allá del auto", "Talent beyond the car"],
  ["Personalidad / carisma", "Personality / charisma"], ["Escudería / equipo", "Team"],
  ["50% auto / 50% piloto", "50% car / 50% driver"], ["Auto / tecnología", "Car / technology"],
  ["Piloto / talento", "Driver / talent"], ["Sí: el auto distorsiona", "Yes: the car distorts results"],
  ["No: las estadísticas son objetivas", "No: statistics are objective"], ["Casi nada", "Very little"]
]);

let records = [];
let activeVariable = "age";

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[character]);

function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') { field += '"'; index += 1; }
      else if (character === '"') quoted = false;
      else field += character;
    } else if (character === '"') quoted = true;
    else if (character === ",") { row.push(field.trim()); field = ""; }
    else if (character === "\n") { row.push(field.trim()); rows.push(row); row = []; field = ""; }
    else if (character !== "\r") field += character;
  }
  if (field || row.length) { row.push(field.trim()); rows.push(row); }
  return rows.filter((values) => values.some(Boolean));
}

function colorFor(value) {
  let hash = 0;
  for (const character of value) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  return `hsl(${Math.abs(hash * 137.508) % 360} 72% 58%)`;
}

function cramersV(sourceRecords, variableKey, choices) {
  const groups = [...new Set(sourceRecords.map((record) => record.values[variableKey]))];
  if (groups.length < 2 || choices.length < 2) return 0;
  const voteRows = weightedVoteRows(sourceRecords, choices.filter((choice) => choice !== "Otros"));
  const table = groups.map((group) => choices.map((choice) => voteRows
    .filter((record) => record.values[variableKey] === group && record.driver === choice)
    .reduce((sum, record) => sum + record.weight, 0)));
  const rowTotals = table.map((row) => row.reduce((sum, value) => sum + value, 0));
  const columnTotals = choices.map((_, index) => table.reduce((sum, row) => sum + row[index], 0));
  const total = rowTotals.reduce((sum, value) => sum + value, 0);
  let chiSquare = 0;
  table.forEach((row, rowIndex) => row.forEach((observed, columnIndex) => {
    const expected = rowTotals[rowIndex] * columnTotals[columnIndex] / total;
    if (expected > 0) chiSquare += ((observed - expected) ** 2) / expected;
  }));
  const denominator = total * Math.min(groups.length - 1, choices.length - 1);
  return denominator > 0 ? Math.sqrt(chiSquare / denominator) : 0;
}

function translatedValue(value, language) {
  if (language !== "en") return value;
  return value.split(" + ").map((part) => englishValues.get(part) ?? part).join(" + ");
}

function associationLabel(value, language) {
  if (language === "es") return value < .1 ? "muy débil" : value < .3 ? "débil" : value < .5 ? "moderada" : "fuerte";
  return value < .1 ? "very weak" : value < .3 ? "weak" : value < .5 ? "moderate" : "strong";
}

function renderCorrelation(topChoices, language) {
  const correlation = document.querySelector("#survey-correlation");
  const voteRows = weightedVoteRows(records, topChoices);
  const choices = [...new Set(voteRows.map((record) => record.driver))];
  const groups = [...new Set(records.map((record) => record.values[activeVariable]))];
  const value = cramersV(records, activeVariable, choices);
  correlation.innerHTML = `<div class="survey-association"><div><span>${language === "es" ? "ASOCIACIÓN EXPLORATORIA" : "EXPLORATORY ASSOCIATION"}</span><strong>Cramér's V ${value.toFixed(2)} · ${associationLabel(value, language)}</strong></div><p>${language === "es" ? "Describe solamente esta muestra y conserva un peso total de uno por persona." : "This describes this sample only and preserves a total weight of one per respondent."}</p></div><div class="survey-legend">${choices.map((choice) => `<span><i style="background:${colorFor(choice)}"></i>${escapeHtml(choice === "Otros" && language === "en" ? "Others" : choice)}</span>`).join("")}</div><div class="survey-groups">${groups.map((group) => {
    const groupRecords = records.filter((record) => record.values[activeVariable] === group);
    const groupVotes = voteRows.filter((record) => record.values[activeVariable] === group);
    return `<div class="survey-group"><div><strong>${escapeHtml(translatedValue(group, language))}</strong><span>${groupRecords.length} ${language === "es" ? (groupRecords.length === 1 ? "respuesta" : "respuestas") : (groupRecords.length === 1 ? "response" : "responses")}</span></div><div class="survey-stack">${choices.map((choice) => {
      const count = groupVotes.filter((record) => record.driver === choice).reduce((sum, record) => sum + record.weight, 0);
      return count ? `<i style="width:${count / groupRecords.length * 100}%;background:${colorFor(choice)}" title="${escapeHtml(choice)}: ${voteFormat.format(count)}"></i>` : "";
    }).join("")}</div></div>`;
  }).join("")}</div>`;
}

function render() {
  if (!records.length) return;
  const language = document.documentElement.lang === "es" ? "es" : "en";
  const ranking = weightedRanking(records);
  const topChoices = ranking.slice(0, 5).map(([driver]) => driver);
  const leaderCount = ranking[0]?.[1] || 1;
  target.innerHTML = `<div class="survey-summary"><div class="survey-total"><strong>${records.length}</strong><span>${language === "es" ? "personas · 1 voto total por persona" : "respondents · 1 total vote per person"}</span></div><div class="survey-ranking">${ranking.map(([driver, count], index) => `<div class="survey-rank-row"><span>${index + 1}</span><strong>${escapeHtml(driver)}</strong><div class="survey-track"><i style="width:${count / leaderCount * 100}%;background:${colorFor(driver)}"></i></div><b>${voteFormat.format(count)}</b><em>${percentFormat.format(count / records.length)}</em></div>`).join("")}</div></div><div class="survey-control"><label for="survey-variable">${language === "es" ? "Cruzar la elección del GOAT por" : "Break down the GOAT choice by"}</label><select id="survey-variable">${surveyVariables.map((variable) => `<option value="${variable.key}">${escapeHtml(language === "es" ? variable.label : variableLabels[variable.key])}</option>`).join("")}</select></div><div id="survey-correlation"></div>`;
  const select = document.querySelector("#survey-variable");
  select.value = activeVariable;
  select.addEventListener("change", () => { activeVariable = select.value; renderCorrelation(topChoices, language); });
  renderCorrelation(topChoices, language);
}

async function loadSurvey() {
  try {
    const [surveyResponse, opinionResponse] = await Promise.all([
      fetch(`${SURVEY_URL}&_=${Date.now()}`, { cache: "no-store" }),
      fetch("../data/opinion-ranking.json")
    ]);
    if (!surveyResponse.ok || !opinionResponse.ok) throw new Error("HTTP error");
    const opinion = await opinionResponse.json();
    const driverNames = [...new Set([...opinion.ranking.map((driver) => driver.name), ...currentDriverNames])];
    records = surveyRecords(parseCsv(await surveyResponse.text()), driverNames);
    render();
  } catch {
    target.innerHTML = `<div class="status error">${document.documentElement.lang === "es" ? "No se pudieron cargar las respuestas en vivo." : "The live survey responses could not be loaded."}</div>`;
  }
}

document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => queueMicrotask(render)));
loadSurvey();
window.setInterval(loadSurvey, 60000);
