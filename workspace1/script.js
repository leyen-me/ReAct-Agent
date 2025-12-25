// Snake Game
// Game variables
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreElement = document.getElementById('score');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const restartBtn = document.getElementById('restartBtn');

const gridSize = 20;
const tileCount = canvas.width / gridSize;

let snake = [
    {x: 10, y: 10}
];
let food = {x: 15, y: 15};
let dx = 0;
let dy = 0;
let score = 0;
let gameRunning = false;
let gamePaused = false;
let gameLoop;

// Initialize game
function initGame() {
    snake = [{x: 10, y: 10}];
    food = generateFood();
    dx = 0;
    dy = 0;
    score = 0;
    scoreElement.textContent = score;
    gameRunning = true;
    gamePaused = false;
    startBtn.textContent = 'Start Game';
    pauseBtn.textContent = 'Pause';
}

// Generate random food position
function generateFood() {
    let newFood;
    let foodOnSnake;
    
    do {
        foodOnSnake = false;
        newFood = {
            x: Math.floor(Math.random() * tileCount),
            y: Math.floor(Math.random() * tileCount)
        };
        
        // Check if food is on snake
        for (let segment of snake) {
            if (segment.x === newFood.x && segment.y === newFood.y) {
                foodOnSnake = true;
                break;
            }
        }
    } while (foodOnSnake);
    
    return newFood;
}

// Draw game elements
function drawGame() {
    // Clear canvas
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw snake
    ctx.fillStyle = '#0fce7c';
    for (let i = 0; i < snake.length; i++) {
        const segment = snake[i];
        // Snake head is slightly different color
        if (i === 0) {
            ctx.fillStyle = '#0fce7c';
        } else {
            ctx.fillStyle = '#0ab369';
        }
        ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize - 2, gridSize - 2);
        
        // Draw eyes on head
        if (i === 0) {
            ctx.fillStyle = '#000';
            // Left eye
            ctx.fillRect(segment.x * gridSize + 5, segment.y * gridSize + 5, 3, 3);
            // Right eye
            ctx.fillRect(segment.x * gridSize + gridSize - 8, segment.y * gridSize + 5, 3, 3);
        }
    }
    
    // Draw food
    ctx.fillStyle = '#ff4757';
    ctx.beginPath();
    ctx.arc(
        food.x * gridSize + gridSize / 2,
        food.y * gridSize + gridSize / 2,
        gridSize / 2 - 1,
        0,
        Math.PI * 2
    );
    ctx.fill();
    
    // Draw grid lines (optional)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i < tileCount; i++) {
        ctx.beginPath();
        ctx.moveTo(i * gridSize, 0);
        ctx.lineTo(i * gridSize, canvas.height);
        ctx.stroke();
        
        ctx.beginPath();
        ctx.moveTo(0, i * gridSize);
        ctx.lineTo(canvas.width, i * gridSize);
        ctx.stroke();
    }
}

// Update game state
function updateGame() {
    if (!gameRunning || gamePaused) return;
    
    // Move snake
    const head = {x: snake[0].x + dx, y: snake[0].y + dy};
    snake.unshift(head);
    
    // Check if snake ate food
    if (head.x === food.x && head.y === food.y) {
        score += 10;
        scoreElement.textContent = score;
        food = generateFood();
    } else {
        snake.pop();
    }
    
    // Check for collisions
    if (checkCollision()) {
        gameOver();
        return;
    }
    
    drawGame();
}

// Check for collisions with walls or self
function checkCollision() {
    const head = snake[0];
    
    // Wall collision
    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
        return true;
    }
    
    // Self collision
    for (let i = 1; i < snake.length; i++) {
        if (head.x === snake[i].x && head.y === snake[i].y) {
            return true;
        }
    }
    
    return false;
}

// Game over
function gameOver() {
    gameRunning = false;
    clearInterval(gameLoop);
    
    // Display game over message
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    ctx.fillStyle = '#ff4757';
    ctx.font = '36px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 30);
    
    ctx.fillStyle = '#fff';
    ctx.font = '24px Arial';
    ctx.fillText(`Final Score: ${score}`, canvas.width / 2, canvas.height / 2 + 20);
    
    startBtn.textContent = 'Start Game';
}

// Start game
function startGame() {
    if (!gameRunning) {
        initGame();
        gameLoop = setInterval(updateGame, 150);
        startBtn.textContent = 'Restart Game';
    } else if (gamePaused) {
        gamePaused = false;
        pauseBtn.textContent = 'Pause';
    }
}

// Pause game
function togglePause() {
    if (!gameRunning) return;
    
    gamePaused = !gamePaused;
    pauseBtn.textContent = gamePaused ? 'Resume' : 'Pause';
}

// Restart game
function restartGame() {
    clearInterval(gameLoop);
    initGame();
    gameLoop = setInterval(updateGame, 150);
}

// Handle keyboard input
function handleKeyPress(e) {
    // Spacebar to start/pause game
    if (e.keyCode === 32) {
        e.preventDefault(); // Prevent spacebar from scrolling the page
        if (!gameRunning) {
            startGame(); // Start the game if not running
        } else {
            togglePause(); // Toggle pause if game is running
        }
        return; // Exit early to avoid other key processing
    }
    
    if (!gameRunning || gamePaused) return;
    
    // Prevent default behavior for arrow keys
    if ([37, 38, 39, 40, 65, 87, 83, 68].includes(e.keyCode)) {
        e.preventDefault();
    }
    
    // Left arrow or A
    if ((e.keyCode === 37 || e.keyCode === 65) && dx !== 1) {
        dx = -1;
        dy = 0;
    }
    // Up arrow or W
    else if ((e.keyCode === 38 || e.keyCode === 87) && dy !== 1) {
        dx = 0;
        dy = -1;
    }
    // Right arrow or D
    else if ((e.keyCode === 39 || e.keyCode === 68) && dx !== -1) {
        dx = 1;
        dy = 0;
    }
    // Down arrow or S
    else if ((e.keyCode === 40 || e.keyCode === 83) && dy !== -1) {
        dx = 0;
        dy = 1;
    }
}

// Event listeners
startBtn.addEventListener('click', startGame);
pauseBtn.addEventListener('click', togglePause);
restartBtn.addEventListener('click', restartGame);

document.addEventListener('keydown', handleKeyPress);

// Initial draw
drawGame();