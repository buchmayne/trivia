// clouds.js
class Cloud {
    constructor(element) {
        this.element = element;
        this.x = Math.random() * window.innerWidth;
        this.y = Math.random() * window.innerHeight * 0.8;
        this.speed = 0.5 + Math.random() * 0.5;
        this.depth = Math.random();
        this.init();
    }

    init() {
        this.element.style.transform = `translate(${this.x}px, ${this.y}px)`;
        this.move();
    }

    move() {
        this.x -= this.speed;
        if (this.x < -this.element.offsetWidth) {
            this.x = window.innerWidth + this.element.offsetWidth;
            this.y = Math.random() * window.innerHeight * 0.8;
        }
        this.element.style.transform = `translate(${this.x}px, ${this.y}px)`;
        requestAnimationFrame(() => this.move());
    }
}

class ParallaxCloud extends Cloud {
    constructor(element) {
        super(element);
        this.handleMouseMove = this.handleMouseMove.bind(this);
        window.addEventListener('mousemove', this.handleMouseMove);
    }

    handleMouseMove(event) {
        const xOffset = (event.clientX - window.innerWidth / 2) * 0.02 * this.depth;
        const yOffset = (event.clientY - window.innerHeight / 2) * 0.02 * this.depth;
        this.element.style.transform = `translate(${this.x + xOffset}px, ${this.y + yOffset}px)`;
    }
}

// Initialize clouds when the document loads
document.addEventListener('DOMContentLoaded', () => {
    const cloudElements = document.querySelectorAll('.cloud');
    cloudElements.forEach(element => new ParallaxCloud(element));
});