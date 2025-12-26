// 贪吃蛇游戏逻辑
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const startButton = document.getElementById('start');
const scoreElement = document.getElementById('score');
const messageElement = document.getElementById('message');

const gridSize = 20;
const tileCount = 20;
let score = 0;

let snake = [
    {x: 10, y: 10}
];
let food = {x: 5, y: 5};
let dx = 0;
let dy = 0;
let gameInterval;
let gameStarted = false;

// 开始游戏
function startGame() {
    if (gameStarted) return;
    
    gameStarted = true;
    score = 0;
    scoreElement.textContent = score;
    messageElement.textContent = '';
    
    snake = [{x: 10, y: 10}];
    food = generateFood();
    dx = 0;
    dy = 0;
    
    gameInterval = setInterval(updateGame, 150);
}

// 生成食物
function generateFood() {
    let newFood;
    let onSnake;
    do {
        onSnake = false;
        newFood = {
            x: Math.floor(Math.random() * tileCount),
            y: Math.floor(Math.random() * tileCount)
        };
        
        // 检查食物是否在蛇身上
        for (let segment of snake) {
            if (segment.x === newFood.x && segment.y === newFood.y) {
                onSnake = true;
                break;
            }
        }
    } while (onSnake);
    
    return newFood;
}

// 更新游戏状态
function updateGame() {
    // 移动蛇
    const head = {x: snake[0].x + dx, y: snake[0].y + dy};
    
    // 检查碰撞
    if (isGameOver(head)) {
        gameOver();
        return;
    }
    
    snake.unshift(head);
    
    // 吃到食物
    if (head.x === food.x && head.y === food.y) {
        score += 10;
        scoreElement.textContent = score;
        food = generateFood();
    } else {
        snake.pop();
    }
    
    drawGame();
}

// 绘制游戏
function drawGame() {
    // 清空画布
    ctx.fillStyle = '#eee';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // 绘制蛇
    ctx.fillStyle = 'green';
    for (let segment of snake) {
        ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize - 2, gridSize - 2);
    }
    
    // 绘制蛇头
    ctx.fillStyle = 'darkgreen';
    ctx.fillRect(snake[0].x * gridSize, snake[0].y * gridSize, gridSize - 2, gridSize - 2);
    
    // 绘制食物
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize - 2, gridSize - 2);
}

// 检查游戏结束
function isGameOver(head) {
    // 撞墙
    if (head.x < 0 || head.y < 0 || head.x >= tileCount || head.y >= tileCount) {
        return true;
    }
    
    // 撞到自己
    for (let i = 0; i < snake.length; i++) {
        if (head.x === snake[i].x && head.y === snake[i].y) {
            return true;
        }
    }
    
    return false;
}

// 游戏结束
function gameOver() {
    clearInterval(gameInterval);
    gameStarted = false;
    messageElement.textContent = '游戏结束！按开始重新游戏。';
}

// 键盘控制
document.addEventListener('keydown', function(e) {
    // 如果游戏未开始，按方向键开始游戏
    if (!gameStarted) {
        // 只有方向键才能开始游戏
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            startGame();
            // 设置初始方向
            switch(e.key) {
                case 'ArrowUp':
                    dx = 0;
                    dy = -1;
                    break;
                case 'ArrowDown':
                    dx = 0;
                    dy = 1;
                    break;
                case 'ArrowLeft':
                    dx = -1;
                    dy = 0;
                    break;
                case 'ArrowRight':
                    dx = 1;
                    dy = 0;
                    break;
            }
            return;
        }
    } else {
        // 游戏已经开始，处理方向控制
        switch(e.key) {
            case 'ArrowUp':
                if (dy !== 1) { // 防止反向移动
                    dx = 0;
                    dy = -1;
                }
                break;
            case 'ArrowDown':
                if (dy !== -1) {
                    dx = 0;
                    dy = 1;
                }
                break;
            case 'ArrowLeft':
                if (dx !== 1) {
                    dx = -1;
                    dy = 0;
                }
                break;
            case 'ArrowRight':
                if (dx !== -1) {
                    dx = 1;
                    dy = 0;
                }
                break;
        }
    }
});

// 移除开始按钮的事件监听器（现在通过键盘启动）
// startButton.addEventListener('click', startGame);

// 初始化画面
drawGame();