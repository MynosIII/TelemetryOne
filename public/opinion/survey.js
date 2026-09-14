const key = (value) => String(value ?? "")
  .normalize("NFD")
  .replace(/\p{Diacritic}/gu, "")
  .toLocaleLowerCase("es")
  .replace(/[^a-z0-9]+/g, " ")
  .trim()
  .replace(/\s+/g, " ");

const tidyText = (value) => String(value ?? "")
  .normalize("NFKC")
  .replace(/[^\p{L}\p{N}]+/gu, " ")
  .trim()
  .replace(/\s+/g, " ");

const containsPhrase = (value, phrase) => ` ${key(value)} `.includes(` ${key(phrase)} `);

function singleChoice(options) {
  return (value) => {
    const exact = options.find((option) => option.aliases.some((alias) => key(value) === key(alias)));
    if (exact) return exact.label;
    const contained = options.find((option) => option.aliases.some((alias) => containsPhrase(value, alias)));
    return contained?.label ?? (tidyText(value) || "Sin respuesta");
  };
}

function multipleChoice(options) {
  return (value) => {
    const matches = options.filter((option) => option.aliases.some((alias) => containsPhrase(value, alias)));
    return matches.length ? matches.map((option) => option.label).join(" + ") : tidyText(value) || "Sin respuesta";
  };
}

function normalizeCountry(value) {
  const normalized = key(value);
  if (["argentina", "argenitna"].includes(normalized)) return "Argentina";
  if (normalized === "mexico") return "México";
  const cleaned = tidyText(value);
  return cleaned ? cleaned.toLocaleLowerCase("es").replace(/(^|\s)\p{L}/gu, (letter) => letter.toLocaleUpperCase("es")) : "Sin respuesta";
}

function normalizeTenure(value) {
  const normalized = key(value);
  if (/no consumo|only through social|don t consume/.test(normalized)) return "No sigue / solo redes";
  if (/este ano|this year/.test(normalized)) return "Empezó este año";
  if (/ano pasado|last year/.test(normalized)) return "El año pasado";
  if (/2 a 4|between 1 and 5/.test(normalized)) return "2 a 4 años";
  if (/5 anos o mas|more than 5|far more than five|desde |decada del|uso de razon|^1990$|^50 anos$/.test(normalized)) return "5 años o más";
  return tidyText(value) || "Sin respuesta";
}

const gender = singleChoice([
  { label: "Femenino", aliases: ["Femenino", "Female"] },
  { label: "Masculino", aliases: ["Masculino", "Male"] }
]);

const age = singleChoice([
  { label: "18 a 24", aliases: ["18 a 24", "18 to 24"] },
  { label: "25 a 34", aliases: ["25 a 34", "25 to 34"] },
  { label: "35 a 50", aliases: ["35 a 50", "35 to 50"] },
  { label: "50 o más", aliases: ["50 o más", "50 or older"] }
]);

const follows = singleChoice([
  { label: "Sí", aliases: ["Sí", "Yes"] },
  { label: "Esporádicamente", aliases: ["Esporádicamente", "Sporadically", "Occasionally"] },
  { label: "No", aliases: ["No"] }
]);

const discovery = multipleChoice([
  { label: "Drive to Survive", aliases: ["Drive to Survive"] },
  { label: "Redes sociales / memes", aliases: ["Redes sociales Memes TikTok", "Social media Memes TikTok"] },
  { label: "Piloto de su país", aliases: ["Por la llegada de un piloto de mi país", "A driver from my country"] },
  { label: "Tradición familiar / amigos", aliases: ["Tradición familiar Amigos", "Family tradition Friends"] },
  { label: "Siempre siguió el automovilismo", aliases: ["Sigo el automovilismo desde siempre", "I ve always followed motorsport"] }
]);

const media = multipleChoice([
  { label: "TV / F1 TV", aliases: ["Televisión Transmisiones oficiales", "TV broadcasts F1 TV", "F1 TV"] },
  { label: "TikTok / Reels", aliases: ["TikTok Reels"] },
  { label: "X / Twitter", aliases: ["X Twitter"] },
  { label: "YouTube / Twitch", aliases: ["YouTube Twitch"] },
  { label: "Foros / Discord / Reddit", aliases: ["Foros Discord Reddit", "Forums Discord Reddit"] },
  { label: "Instagram / app de F1", aliases: ["Aplicación de la F1 Instagram", "F1 app Instagram"] },
  { label: "No consume", aliases: ["No consumo", "None"] }
]);

const otherSeries = multipleChoice([
  { label: "Ninguna", aliases: ["Ninguna", "None"] },
  { label: "F2", aliases: ["F2"] },
  { label: "F3 / F4", aliases: ["F3 F4"] },
  { label: "Fórmula E", aliases: ["Formula E"] },
  { label: "F1 Academy", aliases: ["F1 Academy"] },
  { label: "Turismo Carretera", aliases: ["Turismo Carretera"] },
  { label: "IndyCar", aliases: ["IndyCar"] },
  { label: "WEC", aliases: ["WEC"] },
  { label: "WRC", aliases: ["WRC"] },
  { label: "NASCAR", aliases: ["NASCAR"] },
  { label: "Karting", aliases: ["Karting"] },
  { label: "TC2000 / TN", aliases: ["TC 2000 TN"] },
  { label: "Otras ocasionalmente", aliases: ["Muy eventualmente las demás", "The other categories at present only very occasionally"] }
]);

const criteria = multipleChoice([
  { label: "Resultados", aliases: ["cantidad de títulos y carreras", "Total number of championship titles and race wins"] },
  { label: "Talento más allá del auto", aliases: ["talento al manejar más allá del auto", "Pure talent winning or standing out besides using inferior cars"] },
  { label: "Personalidad / carisma", aliases: ["personalidad carisma o estilo", "Personality charisma and cultural impact"] },
  { label: "Escudería / equipo", aliases: ["escudería equipo", "Team they drive for"] }
]);

const carWeight = singleChoice([
  { label: "50% auto / 50% piloto", aliases: ["Un 50% y 50% equivalente entre auto y piloto", "50% 50%"] },
  { label: "Auto / tecnología", aliases: ["El auto la tecnología de la escudería", "The car team technology"] },
  { label: "Piloto / talento", aliases: ["El talento y habilidad del piloto", "Driver talent and ability"] }
]);

const fairness = singleChoice([
  { label: "Sí: el auto distorsiona", aliases: ["Sí totalmente El auto distorsiona las estadísticas reales", "Yes the car distorts real driver statistics"] },
  { label: "No: las estadísticas son objetivas", aliases: ["No Las estadísticas son lo único objetivo", "No statistics are the only objective measure"] }
]);

const statistics = singleChoice([
  { label: "Fundamental", aliases: ["Fundamental"] },
  { label: "Casi nada", aliases: ["Casi nada", "Very little"] }
]);

export const surveyVariables = [
  { key: "country", label: "País", esHeader: "País", enHeader: "Country of residence", normalize: normalizeCountry },
  { key: "gender", label: "Género", esHeader: "Género", enHeader: "Gender", normalize: gender },
  { key: "age", label: "Edad", esHeader: "Edad", enHeader: "Age", normalize: age },
  { key: "follows", label: "Sigue la F1", esHeader: "Seguís la Formula 1", enHeader: "Do you follow Formula 1", normalize: follows },
  { key: "discovery", label: "Cómo llegó a la F1", esHeader: "Cómo empezaste a seguir la F1", enHeader: "How did you start following Formula 1", normalize: discovery },
  { key: "years", label: "Antigüedad como fan", esHeader: "Hace cuánto ves o seguís", enHeader: "How long have you been following F1", normalize: normalizeTenure },
  { key: "media", label: "Medios que consume", esHeader: "En qué medios o plataformas", enHeader: "Which sources media", normalize: media },
  { key: "otherSeries", label: "Otras categorías", esHeader: "otras categorías del automovilismo", enHeader: "other motorsport categories", normalize: otherSeries },
  { key: "criteria", label: "Criterio para elegir al mejor", esHeader: "en qué te basás principalmente", enHeader: "what attribute do you value", normalize: criteria },
  { key: "carWeight", label: "Peso del auto vs. piloto", esHeader: "qué pesa más en el resultado", enHeader: "biggest impact on winning", normalize: carWeight },
  { key: "fairness", label: "¿Títulos/victorias son injustos?", esHeader: "contar solo las victorias títulos", enHeader: "unfair to compare eras", normalize: fairness },
  { key: "statistics", label: "Valor dado a estadísticas", esHeader: "estadísticas procesadas", enHeader: "weight do you give to advanced statistics", normalize: statistics }
];

const preferredSurnameAliases = [
  ["Juan Manuel Fangio", ["juan fangio", "juan manuel fangio", "fangio"]],
  ["Ayrton Senna", ["senna"]],
  ["Michael Schumacher", ["schumacher", "schumi"]],
  ["Lewis Hamilton", ["hamilton"]],
  ["Max Verstappen", ["verstappen", "verstapen", "vesrtappen"]],
  ["Fernando Alonso", ["alonso"]],
  ["Lando Norris", ["norris"]],
  ["Niki Lauda", ["lauda"]],
  ["Alain Prost", ["prost"]],
  ["Jim Clark", ["jim clark"]],
  ["Sebastian Vettel", ["vettel"]],
  ["Gilles Villeneuve", ["gilles villeneuve"]]
];

function canonicalDisplayName(name) {
  return key(name) === "juan fangio" ? "Juan Manuel Fangio" : name;
}

function driverAliases(driverNames) {
  const names = [...new Set(driverNames.filter(Boolean))];
  const surnameCounts = new Map();
  names.forEach((name) => {
    const surname = key(name).split(" ").at(-1);
    if (surname.length >= 4) surnameCounts.set(surname, (surnameCounts.get(surname) ?? 0) + 1);
  });
  const aliases = names.flatMap((name) => {
    const full = key(name);
    const surname = full.split(" ").at(-1);
    const displayName = canonicalDisplayName(name);
    return [{ name: displayName, alias: full }, ...(surnameCounts.get(surname) === 1 ? [{ name: displayName, alias: surname }] : [])];
  });
  preferredSurnameAliases.forEach(([name, values]) => values.forEach((alias) => aliases.push({ name, alias: key(alias) })));
  const availableNames = new Set(names.map(canonicalDisplayName));
  return aliases.filter(({ name }) => availableNames.has(name));
}

export function extractDriverVotes(answer, driverNames) {
  const normalized = ` ${key(answer)} `;
  const candidates = [];
  driverAliases(driverNames).forEach(({ name, alias }) => {
    const needle = ` ${alias} `;
    const position = normalized.indexOf(needle);
    if (position >= 0) {
      const start = position + 1;
      candidates.push({ name, start, end: start + alias.length, length: alias.length });
    }
  });
  const accepted = [];
  candidates.sort((a, b) => b.length - a.length || a.start - b.start).forEach((candidate) => {
    if (accepted.some((match) => candidate.start < match.end && candidate.end > match.start)) return;
    if (!accepted.some((match) => match.name === candidate.name)) accepted.push(candidate);
  });
  const matches = accepted.sort((a, b) => a.start - b.start).map(({ name }) => name);
  if (matches.length) return matches;
  const fallback = tidyText(answer);
  return fallback ? [fallback.length > 38 ? `${fallback.slice(0, 35)}…` : fallback] : [];
}

function headerIndex(headers, fragment) {
  const needle = key(fragment);
  return headers.findIndex((header) => key(header).includes(needle));
}

function localizedValue(row, indexes, language) {
  const preferred = language === "en" ? indexes.en : indexes.es;
  const fallback = language === "en" ? indexes.es : indexes.en;
  return String(row[preferred] ?? "").trim() || String(row[fallback] ?? "").trim();
}

export function surveyRecords(rows, driverNames) {
  if (!rows.length) return [];
  const headers = rows[0];
  const languageIndex = headerIndex(headers, "Idioma Language");
  const driverIndexes = {
    es: headerIndex(headers, "mejor piloto de la historia de la F1"),
    en: headerIndex(headers, "greatest driver of all time")
  };
  const indexes = Object.fromEntries(surveyVariables.map((variable) => [variable.key, {
    es: headerIndex(headers, variable.esHeader),
    en: headerIndex(headers, variable.enHeader)
  }]));
  return rows.slice(1).map((row) => {
    const declaredLanguage = key(row[languageIndex]);
    const language = declaredLanguage.includes("english") || (!row[driverIndexes.es] && row[driverIndexes.en]) ? "en" : "es";
    const votes = extractDriverVotes(localizedValue(row, driverIndexes, language), driverNames);
    return {
      votes,
      values: Object.fromEntries(surveyVariables.map((variable) => {
        const raw = localizedValue(row, indexes[variable.key], language);
        return [variable.key, raw ? variable.normalize(raw) : "Sin respuesta"];
      }))
    };
  }).filter((record) => record.votes.length);
}

export function weightedVoteRows(records, topChoices = null) {
  return records.flatMap((record) => record.votes.map((driver) => ({
    ...record,
    driver: topChoices ? (topChoices.includes(driver) ? driver : "Otros") : driver,
    weight: 1 / record.votes.length
  })));
}

export function weightedRanking(records) {
  const counts = new Map();
  weightedVoteRows(records).forEach(({ driver, weight }) => counts.set(driver, (counts.get(driver) ?? 0) + weight));
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es"));
}
