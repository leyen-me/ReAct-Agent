// Snake Game - JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Game variables
    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d');
    const scoreElement = document.getElementById('score');
    const startBtn = document.getElementById('startBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const resetBtn = document.getElementById('resetBtn');
    
    // Game settings
    const gridSize = 20;
    const gridWidth = canvas.width / gridSize;
    const gridHeight = canvas.height / gridSize;
    
    // Game state
    let snake = [];
    let food = {};
    let direction = 'right';
    let nextDirection = 'right';
    let score = 0;
    let gameSpeed = 150; // milliseconds
    let gameRunning = false;
    let gameLoop;
    
    // Initialize game
    function initGame() {
        // Reset snake
        snake = [
            {x: 5, y: 10},
            {x: 4, y: 10},
            {x: 3, y: 10}
        ];
        
        // Generate first food
        generateFood();
        
        // Reset game state
        direction = 'right';
        nextDirection = 'right';
        score = 0;
        scoreElement.textContent = score;
        
        // Draw initial state
        draw();
    }
    
    // Generate food at random position
    function generateFood() {
        // Make sure food doesn't appear on snake
        let foodOnSnake;
        do {
            food = {
                x: Math.floor(Math.random() * gridWidth),
                y: Math.floor(Math.random() * gridHeight)
            };
            
            // Check if food is on snake
            foodOnSnake = snake.some(segment => segment.x === food.x && segment.y === food.y);
        } while (foodOnSnake);
    }
    
    // Draw everything on canvas
    function draw() {
        // Clear canvas
        ctx.fillStyle = '#111';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw snake
        snake.forEach((segment, index) => {
            if (index === 0) {
                // Snake head
                ctx.fillStyle = '#0fcc45';
            } else {
                // Snake body
                ctx.fillStyle = '#0daa3a';
            }
            
            // Draw rounded segments
            ctx.beginPath();
            ctx.roundRect(segment.x * gridSize, segment.y * gridSize, gridSize, gridSize, 4);
            ctx.fill();
            
            // Draw eyes on head
            if (index === 0) {
                ctx.fillStyle = '#000';
                const eyeSize = gridSize / 5;
                
                // Draw eyes based on direction
                let leftEyeX, leftEyeY, rightEyeX, rightEyeY;
                
                if (direction === 'right') {
                    leftEyeX = segment.x * gridSize + gridSize - eyeSize * 2;
                    leftEyeY = segment.y * gridSize + eyeSize * 2;
                    rightEyeX = segment.x * gridSize + gridSize - eyeSize * 2;
                    rightEyeY = segment.y * gridSize + gridSize - eyeSize * 3;
                } else if (direction === 'left') {
                    leftEyeX = segment.x * gridSize + eyeSize;
                    leftEyeY = segment.y * gridSize + eyeSize * 2;
                    rightEyeX = segment.x * gridSize + eyeSize;
                    rightEyeY = segment.y * gridSize + gridSize - eyeSize * 3;
                } else if (direction === 'up') {
                    leftEyeX = segment.x * gridSize + eyeSize * 2;
                    leftEyeY = segment.y * gridSize + eyeSize;
                    rightEyeX = segment.x * gridSize + gridSize - eyeSize * 3;
                    rightEyeY = segment.y * gridSize + eyeSize;
                } else { // down
                    leftEyeX = segment.x * gridSize + eyeSize * 2;
                    leftEyeY = segment.y * gridSize + gridSize - eyeSize * 2;
                    rightEyeX = segment.x * gridSize + gridSize - eyeSize * 3;
                    rightEyeY = segment.y * gridSize + gridSize - eyeSize * 2;
                }
                
                ctx.beginPath();
                ctx.arc(leftEyeX, leftEyeY, eyeSize, 0, Math.PI * 2);
                ctx.fill();
                
                ctx.beginPath();
                ctx.arc(rightEyeX, rightEyeY, eyeSize, 0, Math.PI * 2);
                ctx.fill();
            }
        });
        
        // Draw food
        ctx.fillStyle = '#ff4444';
        ctx.beginPath();
        ctx.arc(
            food.x * gridSize + gridSize / 2,
            food.y * gridSize + gridSize / 2,
            gridSize / 2,
            0,
            Math.PI * 2
        );
        ctx.fill();
        
        // Draw grid (optional, for visual reference)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 0.5;
        
        // Vertical lines
        for (let x = 0; x < canvas.width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
        }
        
        // Horizontal lines
        for (let y = 0; y < canvas.height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
    }
    
    // Update game state
    function update() {
        // Update direction
        direction = nextDirection;
        
        // Calculate new head position
        const head = {...snake[0]};
        
        switch (direction) {
            case 'up':
                head.y -= 1;
                break;
            case 'down':
                head.y += 1;
                break;
            case 'left':
                head.x -= 1;
                break;
            case 'right':
                head.x += 1;
                break;
        }
        
        // Check wall collision
        if (head.x < 0 || head.x >= gridWidth || head.y < 0 || head.y >= gridHeight) {
            gameOver();
            return;
        }
        
        // Check self collision
        for (let i = 0; i < snake.length; i++) {
            if (snake[i].x === head.x && snake[i].y === head.y) {
                gameOver();
                return;
            }
        }
        
        // Add new head to snake
        snake.unshift(head);
        
        // Check food collision
        if (head.x === food.x && head.y === food.y) {
            // Increase score
            score += 10;
            scoreElement.textContent = score;
            
            // Generate new food
            generateFood();
            
            // Increase speed slightly every 5 foods
            if (score % 50 === 0 && gameSpeed > 50) {
                gameSpeed -= 10;
                clearInterval(gameLoop);
                gameLoop = setInterval(gameStep, gameSpeed);
            }
        } else {
            // Remove tail if no food eaten
            snake.pop();
        }
        
        // Draw updated game state
        draw();
    }
    
    // Main game step
    function gameStep() {
        if (gameRunning) {
            update();
        }
    }
    
    // Start game
    function startGame() {
        if (!gameRunning) {
            gameRunning = true;
            startBtn.textContent = 'Restart';
            pauseBtn.textContent = 'Pause';
            pauseBtn.disabled = false;
            
            if (gameLoop) {
                clearInterval(gameLoop);
            }
            
            gameLoop = setInterval(gameStep, gameSpeed);
        } else {
            // Restart game if already running
            resetGame();
            startGame();
        }
    }
    
    // Pause/Resume game
    function pauseGame() {
        if (gameRunning) {
            gameRunning = false;
            pauseBtn.textContent = 'Resume';
        } else {
            gameRunning = true;
            pauseBtn.textContent = 'Pause';
        }
    }
    
    // Reset game
    function resetGame() {
        gameRunning = false;
        startBtn.textContent = 'Start Game';
        pauseBtn.textContent = 'Pause';
        pauseBtn.disabled = true;
        
        if (gameLoop) {
            clearInterval(gameLoop);
            gameLoop = null;
        }
        
        // Reset game speed
        gameSpeed = 150;
        
        initGame();
    }
    
    // Game over
    function gameOver() {
        gameRunning = false;
        startBtn.textContent = 'Start Game';
        pauseBtn.textContent = 'Pause';
        pauseBtn.disabled = true;
        
        if (gameLoop) {
            clearInterval(gameLoop);
        }
        
        // Display game over message
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#ff4444';
        ctx.font = 'bold 36px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 30);
        
        ctx.fillStyle = '#fff';
        ctx.font = '24px Arial';
        ctx.fillText(`Score: ${score}`, canvas.width / 2, canvas.height / 2 + 20);
        
        ctx.font = '18px Arial';
        ctx.fillText('Click "Start Game" to play again', canvas.width / 2, canvas.height / 2 + 60);
    }
    
    // Handle keyboard input
    document.addEventListener('keydown', function(event) {
        switch (event.key) {
            case 'ArrowUp':
                if (direction !== 'down') nextDirection = 'up';
                event.preventDefault();
                break;
            case 'ArrowDown':
                if (direction !== 'up') nextDirection = 'down';
                event.preventDefault();
                break;
            case 'ArrowLeft':
                if (direction !== 'right') nextDirection = 'left';
                event.preventDefault();
                break;
            case 'ArrowRight':
                if (direction !== 'left') nextDirection = 'right';
                event.preventDefault();
                break;
            case ' ':
                // Space bar toggles pause
                if (gameRunning) {
                    pauseGame();
                }
                event.preventDefault();
                break;
        }
    });
    
    // Button event listeners
    startBtn.addEventListener('click', startGame);
    pauseBtn.addEventListener('click', pauseGame);
    resetBtn.addEventListener('click', resetGame);
    
    // Initialize the game
    initGame();
    
    // Add rounded rectangle support for older browsers
    if (!CanvasRenderingContext2D.prototype.roundRect) {
        CanvasRenderingContext2D.prototype.roundRect = function(x, y, width, height, radius) {
            if (width < 2 * radius) radius = width / 2;
            if (height < 2 * radius) radius = height / 2;
            
            this.moveTo(x + radius, y);
            this.arcTo(x + width, y, x + width, y + height, radius);
            this.arcTo(x + width, y + height, x, y + height, radius);
            this.arcTo(x, y + height, x, y, radius);
            this.arcTo(x, y, x + width, y, radius);
            this.closePath();
            
            return this;
        };
    }
});