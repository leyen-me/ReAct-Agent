// 极简贪吃蛇
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreDisplay = document.getElementById('score');
const startBtn = document.getElementById('startBtn');

const gridSize = 20;
const tileCount = 20;
let snake = [{x: 10, y: 10}];
let food = {x: 5, y: 5};
let dx = 0, dy = 0;
let score = 0;
let gameRunning = false;
let gameSpeed = 100;

function generateFood() {
    food = {x: Math.floor(Math.random() * tileCount), y: Math.floor(Math.random() * tileCount)};
    for (let s of snake) if (s.x === food.x && s.y === food.y) return generateFood();
}

function draw() {
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'lime';
    for (let s of snake) ctx.fillRect(s.x * gridSize, s.y * gridSize, gridSize - 1, gridSize - 1);
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize - 1, gridSize - 1);
}

function update() {
    const head = {x: snake[0].x + dx, y: snake[0].y + dy};
    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount || snake.some(s => s.x === head.x && s.y === head.y)) {
        gameOver(); return;
    }
    snake.unshift(head);
    if (head.x === food.x && head.y === food.y) {
        score += 10;
        scoreDisplay.textContent = '得分: ' + score;
        generateFood();
        if (score % 50 === 0) gameSpeed = Math.max(50, gameSpeed - 10);
    } else snake.pop();
}

function updateAndDraw() { update(); draw(); }

function gameOver() {
    clearInterval(gameLoop);
    gameRunning = false;
    startBtn.textContent = '重新开始';
    alert('游戏结束！得分: ' + score);
}

function startGame() {
    if (gameRunning) return;
    snake = [{x: 10, y: 10}]; dx = 0; dy = 0; score = 0; generateFood();
    gameRunning = true; gameLoop = setInterval(updateAndDraw, gameSpeed); startBtn.textContent = '游戏中';
}

document.addEventListener('keydown', e => {
    if (!gameRunning) { startGame(); return; }
    if (e.key === 'ArrowUp' && dy !== 1) { dx = 0; dy = -1; }
    if (e.key === 'ArrowDown' && dy !== -1) { dx = 0; dy = 1; }
    if (e.key === 'ArrowLeft' && dx !== 1) { dx = -1; dy = 0; }
    if (e.key === 'ArrowRight' && dx !== -1) { dx = 1; dy = 0; }
});

startBtn.addEventListener('click', startGame);
draw();
