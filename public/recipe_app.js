const recipesData = {
    korean_nuggets: {
        title: "Högprotein Koreanska Chicken Nuggets",
        category: "middag",
        time: "20 min",
        protein: 35,
        calories: 450,
        carbs: 45,
        fat: 12,
        image: "img_korean_nuggets.png",
        desc: "Krispiga nuggets ugnsbakade för minimalt fett, vända i en smakrik och stark gochujangglaze."
    },
    chicken_pasta: {
        title: "Krämig Kycklingpasta med Thailändsk Basilika",
        category: "lunch",
        time: "20 min",
        protein: 45,
        calories: 590,
        carbs: 75,
        fat: 11,
        image: "img_chicken_pasta.png",
        desc: "Krämig pasta där grädden byts ut mot lättkvarg för lägre fetthalt och mer protein, smaksatt med färsk basilika."
    },
    overnight_oats: {
        title: "Proteinboostad Gröt med Äggvita och Kvarg",
        category: "frukost",
        time: "5 min",
        protein: 32,
        calories: 310,
        carbs: 38,
        fat: 3.5,
        image: "img_overnight_oats.png",
        desc: "Havregrynsgröt förstärkt med äggvita och krämig lättkvarg för ett kalorisnålt men extremt mättande mål."
    },
    pea_falafel: {
        title: "Gula Ärter Falafel med Rågsikts-Tunnbröd",
        category: "lunch",
        time: "30 min",
        protein: 28,
        calories: 520,
        carbs: 85,
        fat: 4,
        image: "img_pea_falafel.png",
        desc: "Ugnsbakad falafel på svenska gula ärter som ger maximalt med protein per krona, i hembakat tunnbröd."
    },
    faux_pizza: {
        title: "Proteinrik Faux-Pizza på Havresmet och Kvarg",
        category: "middag",
        time: "15 min",
        protein: 42,
        calories: 480,
        carbs: 32,
        fat: 14,
        image: "img_faux-pizza.png",
        desc: "En proteinsnabb pizza med en botten gjord på havremjöl och äggvita, klar på en kvart."
    },
    oat_bar: {
        title: "Bakad Högprotein-Havrebar med Whey-80",
        category: "frukost",
        time: "20 min",
        protein: 18,
        calories: 220,
        carbs: 26,
        fat: 4,
        image: "img_oat_bar.png",
        desc: "Praktiska bars bakade på havregryn och Whey-80, utmärkta för billigt och smidigt mellanmål."
    }
};

document.addEventListener("DOMContentLoaded", () => {
    // Tab filter logic for recipe grid
    const tabs = document.querySelectorAll('.tab-btn');
    const cards = document.querySelectorAll('.recipe-card');

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            tabs.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            
            const filter = btn.dataset.filter;
            cards.forEach(card => {
                if (filter === 'alla' || card.dataset.cat === filter) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
});
