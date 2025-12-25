const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const scoreElement = document.getElementById('score');

// 游戏设置
const gridSize = 20;
const tileCount = 20;
let score = 0;

// 蛇的初始位置（长度固定为5）
let snake = [
    {x: 12, y: 10},
    {x: 11, y: 10},
    {x: 10, y: 10},
    {x: 9, y: 10},
    {x: 8, y: 10}
];

// 食物的初始位置
let food = {
    x: 5,
    y: 5
};

// 移动方向
let dx = 1; // 初始向右
let dy = 0;

// 游戏状态：preparing(准备中) 或 playing(进行中)
let gameState = "preparing";

// 边界安全区域（留出一圈墙壁）
const safeMin = 1;
const safeMax = tileCount - 2;

// 在安全区域内移动
function moveSafely() {
    const head = snake[0];
    
    // 如果蛇在安全区域内，保持当前方向
    if (head.x > safeMin && head.x < safeMax && head.y > safeMin && head.y < safeMax) {
        // 有小概率改变方向
        if (Math.random() < 0.05) {
            // 随机选择水平或垂直移动
            if (Math.random() < 0.5) {
                dx = dx !== 0 ? dx : (Math.random() < 0.5 ? 1 : -1);
                dy = 0;
            } else {
                dx = 0;
                dy = dy !== 0 ? dy : (Math.random() < 0.5 ? 1 : -1);
            }
        }
        // 保持当前方向
        return;
    }
    
    // 如果接近边界，调整方向远离墙壁
    if (head.x <= safeMin) {
        dx = 1; // 向右
        dy = 0;
    } else if (head.x >= safeMax) {
        dx = -1; // 向左
        dy = 0;
    } else if (head.y <= safeMin) {
        dx = 0;
        dy = 1; // 向下
    } else if (head.y >= safeMax) {
        dx = 0;
        dy = -1; // 向上
    }
}

// 游戏循环
function gameLoop() {
    // 在准备状态，蛇在安全区域内移动
    if (gameState === "preparing") {
        moveSafely();
    }
    
    // 更新蛇的位置
    updateSnake();
    
    // 检查是否碰撞
    if (isGameOver()) {
        resetGame();
        return;
    }
    
    // 绘制
    draw();
    
    // 重复循环
    setTimeout(gameLoop, 100);
}

// 更新蛇的位置
function updateSnake() {
    // 计算新头位置
    const head = {x: snake[0].x + dx, y: snake[0].y + dy};

    // 添加新头
    snake.unshift(head);

    // 检查是否吃到食物
    if (head.x === food.x && head.y === food.y) {
        // 重新生成食物
        generateFood();
    } else {
        // 没吃到就移除尾巴（保持长度不变）
        snake.pop();
    }
}

// 绘制所有元素
function draw() {
    // 清空画布
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制蛇
    ctx.fillStyle = 'lime';
    snake.forEach(segment => {
        ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize - 2, gridSize - 2);
    });

    // 绘制食物
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize - 2, gridSize - 2);
}

// 检查游戏结束
function isGameOver() {
    const head = snake[0];

    // 检查是否撞墙
    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
        return true;
    }

    // 检查是否撞到自己（正式游戏时才检测）
    if (gameState === "playing") {
        for (let i = 1; i < snake.length; i++) {
            if (head.x === snake[i].x && head.y === snake[i].y) {
                return true;
            }
        }
    }

    return false;
}

// 重新开始游戏
function resetGame() {
    alert('游戏结束！你的得分: ' + score);
    // 重置为准备状态
    snake = [
        {x: 12, y: 10},
        {x: 11, y: 10},
        {x: 10, y: 10},
        {x: 9, y: 10},
        {x: 8, y: 10}
    ];
    food = {x: 5, y: 5};
    dx = 1;
    dy = 0;
    score = 0;
    scoreElement.textContent = score;
    gameState = "preparing";
}

// 生成食物
function generateFood() {
    // 随机位置
    let x, y;
    do {
        x = Math.floor(Math.random() * tileCount);
        y = Math.floor(Math.random() * tileCount);
    } while (snake.some(segment => segment.x === x && segment.y === y));

    food = {x, y};
}

// 键盘控制
document.addEventListener('keydown', function(e) {
    // 如果是方向键，进入正式游戏模式
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        if (gameState === "preparing") {
            gameState = "playing";
            score = 0;
            scoreElement.textContent = score;
        }
    }
    
    // 只有在正式游戏模式下才响应方向控制
    if (gameState === "playing") {
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

// 初始生成食物
generateFood();
// 开始游戏循环
gameLoop();