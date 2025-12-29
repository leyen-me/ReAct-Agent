// 游戏配置
const gridSize = 20;
const tileCount = 20;
let snake = [{ x: 10, y: 10 }]; // 蛇的初始位置
let food = { x: 5, y: 5 }; // 食物初始位置
let dx = 0;
let dy = 0;
let score = 0;
let gameRunning = false;
let difficultyLevels = {
    slow: 150,   // 慢速
    normal: 100, // 中速（默认）
    fast: 70     // 快速
};
let gameSpeed = difficultyLevels.normal; // 初始速度基于难度

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreDisplay = document.getElementById('score');
const startBtn = document.getElementById('startBtn');

// 生成随机食物位置
function generateFood() {
    food = {
        x: Math.floor(Math.random() * tileCount),
        y: Math.floor(Math.random() * tileCount)
    };
    
    // 确保食物不在蛇身上
    for (let segment of snake) {
        if (segment.x === food.x && segment.y === food.y) {
            return generateFood();
        }
    }
}

// 绘制游戏元素
function draw() {
    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 绘制蛇
    ctx.fillStyle = 'green';
    for (let segment of snake) {
        ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize - 1, gridSize - 1);
    }
    
    // 绘制食物
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize - 1, gridSize - 1);
}

// 更新游戏状态
function update() {
    // 移动蛇头
    const head = { x: snake[0].x + dx, y: snake[0].y + dy };
    
    // 检查边界碰撞
    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
        gameOver();
        return;
    }
    
    // 检查自我碰撞
    for (let i = 1; i < snake.length; i++) {
        if (head.x === snake[i].x && head.y === snake[i].y) {
            gameOver();
            return;
        }
    }
    
    // 添加新头
    snake.unshift(head);
    
    // 检查是否吃到食物
    if (head.x === food.x && head.y === food.y) {
        score += 10;
        scoreDisplay.textContent = `得分: ${score}`;
        generateFood();
        
        // 每吃到5个食物，速度加快
        if (score % 50 === 0) {
            gameSpeed = Math.max(50, gameSpeed - 10);
            clearInterval(gameLoop);
            gameLoop = setInterval(updateAndDraw, gameSpeed);
        }
    } else {
        // 如果没吃到食物，移除蛇尾
        snake.pop();
    }
}

// 更新和绘制
function updateAndDraw() {
    update();
    draw();
}

// 游戏结束
function gameOver() {
    clearInterval(gameLoop);
    gameRunning = false;
    startBtn.textContent = '重新开始';
    alert(`游戏结束！你的得分是: ${score}`);
}

// 开始游戏
function startGame() {
    if (gameRunning) return;
    
    // 重置游戏状态
    snake = [{ x: 10, y: 10 }];
    dx = 0;
    dy = 0;
    score = 0;
    gameSpeed = difficultyLevels[document.getElementById('difficulty').value] || difficultyLevels.normal;
    scoreDisplay.textContent = '得分: 0';
    generateFood();
    
    // 开始游戏循环
    gameRunning = true;
    gameLoop = setInterval(updateAndDraw, gameSpeed);
    startBtn.textContent = '游戏进行中';
}

// 监听键盘事件
document.addEventListener('keydown', function(e) {
    // 如果游戏未开始，按任意方向键开始游戏
    if (!gameRunning) {
        startGame();
        return;
    }
    
    // 防止蛇直接反向移动
    switch (e.key) {
        case 'ArrowUp':
            if (dy !== 1) { // 不允许向下转为向上
                dx = 0;
                dy = -1;
            }
            break;
        case 'ArrowDown':
            if (dy !== -1) { // 不允许向上转为向下
                dx = 0;
                dy = 1;
            }
            break;
        case 'ArrowLeft':
            if (dx !== 1) { // 不允许向右转为向左
                dx = -1;
                dy = 0;
            }
            break;
        case 'ArrowRight':
            if (dx !== -1) { // 不允许向左转为向右
                dx = 1;
                dy = 0;
            }
            break;
    }
});

// 开始按钮事件
startBtn.addEventListener('click', startGame);

// 初始绘制
draw();
