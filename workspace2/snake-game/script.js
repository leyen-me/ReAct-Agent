const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const scoreElement = document.getElementById('score');
const restartButton = document.getElementById('restart');

const box = 20; // 每个小格子的大小
let score = 0;
let d;

// 创建蛇
let snake = [];
snake[0] = {
    x: 9 * box,
    y: 10 * box
};

// 创建食物
let food = {
    x: Math.floor(Math.random() * 19 + 1) * box,
    y: Math.floor(Math.random() * 19 + 1) * box
};

// 控制蛇
window.addEventListener('keydown', direction);

function direction(event) {
    if(event.keyCode == 37 && d != "RIGHT"){
        d = "LEFT";
    }else if(event.keyCode == 38 && d != "DOWN"){
        d = "UP";
    }else if(event.keyCode == 39 && d != "LEFT"){
        d = "RIGHT";
    }else if(event.keyCode == 40 && d != "UP"){
        d = "DOWN";
    }
}

// 重新开始游戏
restartButton.addEventListener('click', restartGame);

function restartGame() {
    score = 0;
    scoreElement.textContent = score;
    snake = [];
    snake[0] = {
        x: 9 * box,
        y: 10 * box
    };
    food = {
        x: Math.floor(Math.random() * 19 + 1) * box,
        y: Math.floor(Math.random() * 19 + 1) * box
    };
    d = undefined;
    clearInterval(game);
    game = setInterval(draw, 150);
}

// 检查是否吃到食物
function collision(head, array) {
    for(let i = 0; i < array.length; i++) {
        if(head.x == array[i].x && head.y == array[i].y) {
            return true;
        }
    }
    return false;
}

// 绘制游戏
function draw() {
    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 绘制蛇
    for(let i = 0; i < snake.length; i++) {
        ctx.fillStyle = (i == 0) ? "green" : "white";
        ctx.fillRect(snake[i].x, snake[i].y, box, box);
        
        ctx.strokeStyle = "red";
        ctx.strokeRect(snake[i].x, snake[i].y, box, box);
    }
    
    // 绘制食物
    ctx.fillStyle = "red";
    ctx.fillRect(food.x, food.y, box, box);
    
    // 蛇的移动
    let snakeX = snake[0].x;
    let snakeY = snake[0].y;
    
    if(d == "LEFT") snakeX -= box;
    if(d == "UP") snakeY -= box;
    if(d == "RIGHT") snakeX += box;
    if(d == "DOWN") snakeY += box;
    
    // 如果蛇吃到食物
    if(snakeX == food.x && snakeY == food.y) {
        score++;
        scoreElement.textContent = score;
        food = {
            x: Math.floor(Math.random() * 19 + 1) * box,
            y: Math.floor(Math.random() * 19 + 1) * box
        }
        // 不删除蛇尾
    } else {
        // 删除蛇尾
        snake.pop();
    }
    
    // 添加新头
    let newHead = {
        x: snakeX,
        y: snakeY
    };
    
    // 检查是否超出边界或自撞
    if(
        snakeX < 0 || 
        snakeY < 0 || 
        snakeX >= canvas.width || 
        snakeY >= canvas.height || 
        collision(newHead, snake)
    ) {
        clearInterval(game);
        alert("游戏结束！你的得分: " + score);
        return;
    }
    
    snake.unshift(newHead);
}

// 开始游戏
let game = setInterval(draw, 150);