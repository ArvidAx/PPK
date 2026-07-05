# SEO-analys & Prompts för "Protein Per Krona"

Här är två konkreta förbättringar för att optimera [index.html](file:///c:/Users/arvid/Documents/PPK/PPK/public/index.html) för sökordet **"protein per krona"** samt färdiga prompts du kan köra direkt.

---

## Förbättring 1: FAQ-sektion med FAQPage JSON-LD Schema

### Varför detta hjälper:
Sökare som letar efter "protein per krona" har ofta frågor som: *"Vad är ett bra PPK-värde?"*, *"Hur beräknar man PPK?"* och *"Vilken mat ger mest protein per krona?"*. Genom att bygga en interaktiv FAQ-sektion på startsidan och tagga den med Googles officiella **FAQPage Schema (JSON-LD)**, kan webbplatsen få Rich Snippets direkt i sökresultaten (utfällbara frågor under länken), vilket ökar synligheten enormt.

### Prompt för att implementera Förbättring 1:
```text
Du är en SEO-expert och webbutvecklare. Jag vill att du uppdaterar vår kalkylatorsida på `public/index.html` samt vår CSS-fil på `public/style.css` för att lägga till en modern, interaktiv FAQ-sektion (FAQ-dragspel/accordion) och ett tillhörande JSON-LD strukturerat data-schema för FAQPage.

Gör följande ändringar:
1. Lägg till ett nytt JSON-LD script i `<head>` i `index.html` av typen "@type": "FAQPage". Inkludera dessa 3 frågor och svar (anpassa till svenska):
   - Fråga 1: Vad är ett bra Protein Per Krona (PPK) värde?
     Svar: Ett bra PPK-värde för vanlig mat ligger på över 2.0 - 3.0 gram protein per krona. Billiga basvaror som gula ärter, linser och vetemjöl kan nå över 10-12 g/kr, medan billigt proteinpulver (vassle) online ofta ligger runt 2.5 - 3.0 g/kr med mycket hög proteinkoncentration.
   - Fråga 2: Hur beräknar man protein per krona?
     Svar: Formeln för att berävna Protein Per Krona (PPK) är: (Mängd protein per 100g * Förpackningens vikt i kg * 10) / Pris i kr. Det visar exakt hur många gram protein du får för varje spenderad krona.
   - Fråga 3: Vilken mat ger mest protein per krona i svenska butiker?
     Svar: Gula ärter, havregryn, vetemjöl, röda linser, billig kycklingfilé (fryst) och kvarg är exempel på livsmedel med extremt bra PPK i svenska matbutiker som Willys och Hemköp.
2. Skapa en snygg, interaktiv FAQ-sektion i HTML (dragspelsmeny där man kan klicka för att fälla ut svaren) och placera den precis ovanför `<footer>` i `index.html`.
3. Lägg till matchande CSS i `public/style.css` för FAQ-sektionen. Se till att designen följer vår röda accentfärg (#e11d48), använder mjuka övergångar (transitions) vid utfällning, och passar perfekt in i den existerande mörka/ljusa kontrasten på sidan.
4. Lägg till en enkel Vanilla JS-funktion i slutet av `public/app.js` eller inline i `index.html` för att sköta öppning/stängning av FAQ-frågorna med rätt WAI-ARIA-attribut (`aria-expanded="true/false"`) för tillgänglighet.
```

---

## Förbättring 2: Sökordsoptimering av Titlar, Meta & H1

### Varför detta hjälper:
Googles sökalgoritm lägger störst vikt vid de sökord som står först i `<title>`-taggen och i webbplatsens huvudrubrik (`<h1>`). Just nu är titeln *"Billig Proteinrik Mat – Jämför..."*. Genom att flytta "Protein per krona" till absolut första position och lägga till ordet "Kalkylator" matchar vi sökintentionen perfekt.

### Prompt för att implementera Förbättring 2:
```text
Jag vill att du optimerar sökordsrelevansen för "protein per krona" i de viktigaste SEO-taggarna på `public/index.html`. Genomför följande justeringar:

1. Ändra `<title>`-taggen i `<head>` till:
   <title>Protein Per Krona (PPK) Kalkylator – Billig Proteinrik Mat | PPK</title>
2. Ändra `<meta name="description">` till:
   <meta name="description" content="Använd vår Protein Per Krona (PPK) kalkylator för att hitta billigaste proteinrik mat på Willys och Hemköp. Jämför g/kr för över 10 000 produkter dagligen.">
3. Ändra sidans primära `<h1>` (runt rad 70) till:
   <h1 class="app-title">Protein Per Krona (PPK) &ndash; <span class="accent-red">Kalkylator för Billig Mat</span></h1>
4. Uppdatera även Open Graph-taggarna (`og:title` och `og:description`) samt Twitter-kort-taggarna i `<head>` så att de matchar de nya optimerade texterna.
```
