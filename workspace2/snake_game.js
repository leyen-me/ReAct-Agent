// Snake Game JavaScript

document.addEventListener('DOMContentLoaded', () => {
    // Get canvas and context
    const canvas = document.getElementById('game-board');
    if (!canvas) {
        console.error('Canvas not found! Please ensure HTML has <canvas id="game-board">
');
        return;
    }
    const ctx = canvas.getContext('2d');
    canvas.width = 800;
    canvas.height = 600;

    // Game variables
    const gridSize = 20;
    const tiles = 40; // Tiles in [each direction] (increase for more grid)
    canvas.width = gridSize * tiles;
    canvas.height = gridSize * tiles;
    let snake = [{x: 15, y: 15}]; // Starting position
    let food = createFood();
    let dx = 1; // Direction X
    let dy = 0; // Direction Y
    let speed = 100; // Game speed in ms
    let score = 0;
    let gameOver = false;
    let gameRunning = false;

    function createFood() {
        return {
            x: Math.floor(Math.random() * tiles),
            y: Math.floor(Math.random() * tiles)
        };
    }

    function gameLoop() {
        if (!gameRunning) return;

        setTimeout(() => {
            // Move snake
            const head = {x: snake[0].x + dx, y: snake[0].y + dy};
            snake.unshift(head);

            // Check collision with food
            if (head.x === food.x && head.y === food.y) {
                score++;
                food = createFood();
            } else {
                snake.pop(); // Remove tail if no food eaten
            }

            // Check collision with boundaries or self
            if (head.x < 0 || head.x >= tiles || head.y < 0 || head.y >= tiles || 
                snake.some(segment => segment.x === head.x && segment.y === head.y)) {
                gameOver = true;
                alert('Game Over! Score: ' + score);
                clearInterval(gameLoopInterval);
                return;
            }

            // Draw everything
            draw();
            gameLoop(); // Continue loop
        }, speed);
    }

    function draw() {
        // Clear canvas
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw grid for better visualization
        ctx.strokeStyle = '#333';
        for (let i = 0; i <= tiles; i++) {
            ctx.beginPath();
            ctx.moveTo(gridSize * i, 0);
            ctx.lineTo(gridSize * i, canvas.height);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, gridSize * i);
            ctx.lineTo(canvas.width, gridSize * i);
            ctx.stroke();
        }

        // Draw snake
        snake.forEach((segment, index) => {
            ctx.fillStyle = index === 0 ? 'green' : 'lightgreen'; // Head green, body lighter
            ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize - 1, gridSize - 1);
        });

        // Draw food
        ctx.fillStyle = 'red';
        ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize - 1, gridSize - 1);

        // Draw score
        ctx.fillStyle = 'white';
        ctx.font = '24px Arial';
        ctx.fillText('Score: ' + score, 10, 30);
    }

    function startGame() {
        if (gameRunning) return;
        snake = [{x: 15, y: 15}];
        food = createFood();
        dx = 1; dy = 0;
        score = 0;
        gameOver = false;
        gameRunning = true;
        gameLoop();
    }

    function togglePause() {
        if (!gameRunning) return;
        gameRunning = !gameRunning;
        clearInterval(gameLoopInterval);
    }

    function resetGame() {
        clearInterval(gameLoopInterval);
        startGame();
    }

    // Keyboard controls
    document.addEventListener('keydown', (e) => {
        switch (e.key) {
            case 'ArrowUp':
                if (dy === 0) { // Prevent 180-degree turn
                    dx = 0; dy = -1;
                }
                break;
            case 'ArrowDown':
                if (dy === 0) {
                    dx = 0; dy = 1;
                }
                break;
            case 'ArrowLeft':
                if (dx === 0) {
                    dx = -1; dy = 0;
                }
                break;
            case 'ArrowRight':
                if (dx === 0) {
                    dx = 1; dy = 0;
                }
                break;
            case ' ':
                togglePause();
                break;
        }
    });

    // UI buttons from HTML (assuming buttons with IDs)
    document.getElementById('start').addEventListener('click', startGame);
    document.getElementById('pause').addEventListener('click', togglePause);
    document.getElementById('reset').addEventListener('click', resetGame);

    // Initialize draw on load
    draw();
});