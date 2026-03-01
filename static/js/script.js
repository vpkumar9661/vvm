// Create star container
const starContainer = document.createElement("div");
starContainer.classList.add("stars");
document.body.appendChild(starContainer);

// Generate stars
for (let i = 0; i < 120; i++) {
    const star = document.createElement("div");
    star.classList.add("star");

    star.style.top = Math.random() * 100 + "%";
    star.style.left = Math.random() * 100 + "%";
    star.style.animationDuration = (Math.random() * 2 + 2) + "s";
    star.style.opacity = Math.random();

    starContainer.appendChild(star);
}

document.addEventListener("scroll", function() {
    document.querySelectorAll(".fade-in").forEach(function(el) {
        const rect = el.getBoundingClientRect();
        if(rect.top < window.innerHeight - 100){
            el.classList.add("visible");
        }
    });
});

// 3D Parallax Effect
const collage = document.getElementById("collageBox");

collage.addEventListener("mousemove", (e) => {
    const rect = collage.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const rotateY = (x / rect.width - 0.5) * 10;
    const rotateX = (y / rect.height - 0.5) * -10;

    collage.style.transform =
        `rotateY(${rotateY}deg) rotateX(${rotateX}deg)`;
});

collage.addEventListener("mouseleave", () => {
    collage.style.transform = "rotateY(0deg) rotateX(0deg)";
});

const glow = document.querySelector(".cursor-glow");

let mouseX = 0;
let mouseY = 0;
let currentX = 0;
let currentY = 0;

document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
});

function animateGlow() {
    currentX += (mouseX - currentX) * 0.08;
    currentY += (mouseY - currentY) * 0.08;

    glow.style.left = currentX + "px";
    glow.style.top = currentY + "px";

    requestAnimationFrame(animateGlow);
}

animateGlow();
document.querySelectorAll("a, button").forEach(el => {
    el.addEventListener("mouseenter", () => {
        glow.style.width = "650px";
        glow.style.height = "650px";
    });

    el.addEventListener("mouseleave", () => {
        glow.style.width = "500px";
        glow.style.height = "500px";
    });
});

