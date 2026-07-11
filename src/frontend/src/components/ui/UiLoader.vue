<template>
  <div class="container">
    <div class="h1Container">
      <div class="cube h1 w1 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w1 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w1 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w2 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w2 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w2 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w3 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w3 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h1 w3 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>
    </div>

    <div class="h2Container">
      <div class="cube h2 w1 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w1 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w1 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w2 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w2 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w2 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w3 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w3 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h2 w3 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>
    </div>

    <div class="h3Container">
      <div class="cube h3 w1 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w1 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w1 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w2 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w2 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w2 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w3 l1">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w3 l2">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>

      <div class="cube h3 w3 l3">
        <div class="face top"></div>
        <div class="face left"></div>
        <div class="face right"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
body {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100vw;
  margin: 0;
  padding: 0;
  background: #fff;
}

.container {
  position: relative;
  height: 100px;
  width: 86px;
  transform: scale(0.5);
}

.cube {
  position: absolute;
  width: 86px;
  height: 100px;
}

.right {
  background: #bdd5fe;
  transform: rotate(-30deg) skewX(-30deg) translate(49px, 65px) scaleY(0.86);
}

.left {
  background: #013593;
  transform: rotate(90deg) skewX(-30deg) scaleY(0.86) translate(25px, -50px);
}

.top {
  background: #2673fd;
  transform: rotate(210deg) skew(-30deg) translate(-75px, -22px) scaleY(0.86);
  z-index: 2;
}

.face {
  height: 50px;
  width: 50px;
  position: absolute;
  transform-origin: 0 0;
}

.h1.w1.l1 {
  z-index: -1;
  animation-name: h1w1l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w1l1 {
  0% {
    transform: translate(0%, -100%);
  }
  14% {
    transform: translate(-50%, -125%);
  }
  28% {
    transform: translate(0%, -150%);
  }
  43% {
    transform: translate(0%, -200%);
  }
  57% {
    transform: translate(50%, -175%);
  }
  71% {
    transform: translate(0%, -150%);
  }
  85% {
    transform: translate(0%, -100%);
  }
  100% {
    transform: translate(0%, -100%);
  }
}
.h1.w1.l2 {
  z-index: -1;
  animation-name: h1w1l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w1l2 {
  0% {
    transform: translate(50%, -75%);
  }
  14% {
    transform: translate(50%, -75%);
  }
  28% {
    transform: translate(100%, -100%);
  }
  43% {
    transform: translate(100%, -150%);
  }
  57% {
    transform: translate(100%, -150%);
  }
  71% {
    transform: translate(50%, -125%);
  }
  85% {
    transform: translate(50%, -75%);
  }
  100% {
    transform: translate(50%, -75%);
  }
}
.h1.w1.l3 {
  z-index: -1;
  animation-name: h1w1l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w1l3 {
  0% {
    transform: translate(100%, -50%);
  }
  14% {
    transform: translate(150%, -25%);
  }
  28% {
    transform: translate(200%, -50%);
  }
  43% {
    transform: translate(200%, -100%);
  }
  57% {
    transform: translate(150%, -125%);
  }
  71% {
    transform: translate(100%, -100%);
  }
  85% {
    transform: translate(100%, -50%);
  }
  100% {
    transform: translate(100%, -50%);
  }
}
.h1.w2.l1 {
  z-index: -1;
  animation-name: h1w2l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w2l1 {
  0% {
    transform: translate(-50%, -75%);
  }
  14% {
    transform: translate(-100%, -100%);
  }
  28% {
    transform: translate(-100%, -100%);
  }
  43% {
    transform: translate(-100%, -150%);
  }
  57% {
    transform: translate(-50%, -125%);
  }
  71% {
    transform: translate(-50%, -125%);
  }
  85% {
    transform: translate(-50%, -75%);
  }
  100% {
    transform: translate(-50%, -75%);
  }
}
.h1.w2.l2 {
  z-index: -1;
  animation-name: h1w2l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w2l2 {
  0% {
    transform: translate(0%, -50%);
  }
  14% {
    transform: translate(0%, -50%);
  }
  28% {
    transform: translate(0%, -50%);
  }
  43% {
    transform: translate(0%, -100%);
  }
  57% {
    transform: translate(0%, -100%);
  }
  71% {
    transform: translate(0%, -100%);
  }
  85% {
    transform: translate(0%, -50%);
  }
  100% {
    transform: translate(0%, -50%);
  }
}
.h1.w2.l3 {
  z-index: -1;
  animation-name: h1w2l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w2l3 {
  0% {
    transform: translate(50%, -25%);
  }
  14% {
    transform: translate(100%, 0%);
  }
  28% {
    transform: translate(100%, 0%);
  }
  43% {
    transform: translate(100%, -50%);
  }
  57% {
    transform: translate(50%, -75%);
  }
  71% {
    transform: translate(50%, -75%);
  }
  85% {
    transform: translate(50%, -25%);
  }
  100% {
    transform: translate(50%, -25%);
  }
}
.h1.w3.l1 {
  z-index: -1;
  animation-name: h1w3l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w3l1 {
  0% {
    transform: translate(-100%, -50%);
  }
  14% {
    transform: translate(-150%, -75%);
  }
  28% {
    transform: translate(-200%, -50%);
  }
  43% {
    transform: translate(-200%, -100%);
  }
  57% {
    transform: translate(-150%, -75%);
  }
  71% {
    transform: translate(-100%, -100%);
  }
  85% {
    transform: translate(-100%, -50%);
  }
  100% {
    transform: translate(-100%, -50%);
  }
}
.h1.w3.l2 {
  z-index: -1;
  animation-name: h1w3l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w3l2 {
  0% {
    transform: translate(-50%, -25%);
  }
  14% {
    transform: translate(-50%, -25%);
  }
  28% {
    transform: translate(-100%, 0%);
  }
  43% {
    transform: translate(-100%, -50%);
  }
  57% {
    transform: translate(-100%, -50%);
  }
  71% {
    transform: translate(-50%, -75%);
  }
  85% {
    transform: translate(-50%, -25%);
  }
  100% {
    transform: translate(-50%, -25%);
  }
}
.h1.w3.l3 {
  z-index: -1;
  animation-name: h1w3l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h1w3l3 {
  0% {
    transform: translate(0%, 0%);
  }
  14% {
    transform: translate(50%, 25%);
  }
  28% {
    transform: translate(0%, 50%);
  }
  43% {
    transform: translate(0%, 0%);
  }
  57% {
    transform: translate(-50%, -25%);
  }
  71% {
    transform: translate(0%, -50%);
  }
  85% {
    transform: translate(0%, 0%);
  }
  100% {
    transform: translate(0%, 0%);
  }
}
.h2.w1.l1 {
  z-index: -2;
  animation-name: h2w1l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w1l1 {
  0% {
    transform: translate(0%, -50%);
  }
  14% {
    transform: translate(-50%, -75%);
  }
  28% {
    transform: translate(0%, -100%);
  }
  43% {
    transform: translate(0%, -100%);
  }
  57% {
    transform: translate(50%, -75%);
  }
  71% {
    transform: translate(0%, -50%);
  }
  85% {
    transform: translate(0%, -50%);
  }
  100% {
    transform: translate(0%, -50%);
  }
}
.h2.w1.l2 {
  z-index: -2;
  animation-name: h2w1l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w1l2 {
  0% {
    transform: translate(50%, -25%);
  }
  14% {
    transform: translate(50%, -25%);
  }
  28% {
    transform: translate(100%, -50%);
  }
  43% {
    transform: translate(100%, -50%);
  }
  57% {
    transform: translate(100%, -50%);
  }
  71% {
    transform: translate(50%, -25%);
  }
  85% {
    transform: translate(50%, -25%);
  }
  100% {
    transform: translate(50%, -25%);
  }
}
.h2.w1.l3 {
  z-index: -2;
  animation-name: h2w1l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w1l3 {
  0% {
    transform: translate(100%, 0%);
  }
  14% {
    transform: translate(150%, 25%);
  }
  28% {
    transform: translate(200%, 0%);
  }
  43% {
    transform: translate(200%, 0%);
  }
  57% {
    transform: translate(150%, -25%);
  }
  71% {
    transform: translate(100%, 0%);
  }
  85% {
    transform: translate(100%, 0%);
  }
  100% {
    transform: translate(100%, 0%);
  }
}
.h2.w2.l1 {
  z-index: -2;
  animation-name: h2w2l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w2l1 {
  0% {
    transform: translate(-50%, -25%);
  }
  14% {
    transform: translate(-100%, -50%);
  }
  28% {
    transform: translate(-100%, -50%);
  }
  43% {
    transform: translate(-100%, -50%);
  }
  57% {
    transform: translate(-50%, -25%);
  }
  71% {
    transform: translate(-50%, -25%);
  }
  85% {
    transform: translate(-50%, -25%);
  }
  100% {
    transform: translate(-50%, -25%);
  }
}
.h2.w2.l2 {
  z-index: -2;
  animation-name: h2w2l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w2l2 {
  0% {
    transform: translate(0%, 0%);
  }
  14% {
    transform: translate(0%, 0%);
  }
  28% {
    transform: translate(0%, 0%);
  }
  43% {
    transform: translate(0%, 0%);
  }
  57% {
    transform: translate(0%, 0%);
  }
  71% {
    transform: translate(0%, 0%);
  }
  85% {
    transform: translate(0%, 0%);
  }
  100% {
    transform: translate(0%, 0%);
  }
}
.h2.w2.l3 {
  z-index: -2;
  animation-name: h2w2l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w2l3 {
  0% {
    transform: translate(50%, 25%);
  }
  14% {
    transform: translate(100%, 50%);
  }
  28% {
    transform: translate(100%, 50%);
  }
  43% {
    transform: translate(100%, 50%);
  }
  57% {
    transform: translate(50%, 25%);
  }
  71% {
    transform: translate(50%, 25%);
  }
  85% {
    transform: translate(50%, 25%);
  }
  100% {
    transform: translate(50%, 25%);
  }
}
.h2.w3.l1 {
  z-index: -2;
  animation-name: h2w3l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w3l1 {
  0% {
    transform: translate(-100%, 0%);
  }
  14% {
    transform: translate(-150%, -25%);
  }
  28% {
    transform: translate(-200%, 0%);
  }
  43% {
    transform: translate(-200%, 0%);
  }
  57% {
    transform: translate(-150%, 25%);
  }
  71% {
    transform: translate(-100%, 0%);
  }
  85% {
    transform: translate(-100%, 0%);
  }
  100% {
    transform: translate(-100%, 0%);
  }
}
.h2.w3.l2 {
  z-index: -2;
  animation-name: h2w3l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w3l2 {
  0% {
    transform: translate(-50%, 25%);
  }
  14% {
    transform: translate(-50%, 25%);
  }
  28% {
    transform: translate(-100%, 50%);
  }
  43% {
    transform: translate(-100%, 50%);
  }
  57% {
    transform: translate(-100%, 50%);
  }
  71% {
    transform: translate(-50%, 25%);
  }
  85% {
    transform: translate(-50%, 25%);
  }
  100% {
    transform: translate(-50%, 25%);
  }
}
.h2.w3.l3 {
  z-index: -2;
  animation-name: h2w3l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h2w3l3 {
  0% {
    transform: translate(0%, 50%);
  }
  14% {
    transform: translate(50%, 75%);
  }
  28% {
    transform: translate(0%, 100%);
  }
  43% {
    transform: translate(0%, 100%);
  }
  57% {
    transform: translate(-50%, 75%);
  }
  71% {
    transform: translate(0%, 50%);
  }
  85% {
    transform: translate(0%, 50%);
  }
  100% {
    transform: translate(0%, 50%);
  }
}
.h3.w1.l1 {
  z-index: -3;
  animation-name: h3w1l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w1l1 {
  0% {
    transform: translate(0%, 0%);
  }
  14% {
    transform: translate(-50%, -25%);
  }
  28% {
    transform: translate(0%, -50%);
  }
  43% {
    transform: translate(0%, 0%);
  }
  57% {
    transform: translate(50%, 25%);
  }
  71% {
    transform: translate(0%, 50%);
  }
  85% {
    transform: translate(0%, 0%);
  }
  100% {
    transform: translate(0%, 0%);
  }
}
.h3.w1.l2 {
  z-index: -3;
  animation-name: h3w1l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w1l2 {
  0% {
    transform: translate(50%, 25%);
  }
  14% {
    transform: translate(50%, 25%);
  }
  28% {
    transform: translate(100%, 0%);
  }
  43% {
    transform: translate(100%, 50%);
  }
  57% {
    transform: translate(100%, 50%);
  }
  71% {
    transform: translate(50%, 75%);
  }
  85% {
    transform: translate(50%, 25%);
  }
  100% {
    transform: translate(50%, 25%);
  }
}
.h3.w1.l3 {
  z-index: -3;
  animation-name: h3w1l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w1l3 {
  0% {
    transform: translate(100%, 50%);
  }
  14% {
    transform: translate(150%, 75%);
  }
  28% {
    transform: translate(200%, 50%);
  }
  43% {
    transform: translate(200%, 100%);
  }
  57% {
    transform: translate(150%, 75%);
  }
  71% {
    transform: translate(100%, 100%);
  }
  85% {
    transform: translate(100%, 50%);
  }
  100% {
    transform: translate(100%, 50%);
  }
}
.h3.w2.l1 {
  z-index: -3;
  animation-name: h3w2l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w2l1 {
  0% {
    transform: translate(-50%, 25%);
  }
  14% {
    transform: translate(-100%, 0%);
  }
  28% {
    transform: translate(-100%, 0%);
  }
  43% {
    transform: translate(-100%, 50%);
  }
  57% {
    transform: translate(-50%, 75%);
  }
  71% {
    transform: translate(-50%, 75%);
  }
  85% {
    transform: translate(-50%, 25%);
  }
  100% {
    transform: translate(-50%, 25%);
  }
}
.h3.w2.l2 {
  z-index: -3;
  animation-name: h3w2l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w2l2 {
  0% {
    transform: translate(0%, 50%);
  }
  14% {
    transform: translate(0%, 50%);
  }
  28% {
    transform: translate(0%, 50%);
  }
  43% {
    transform: translate(0%, 100%);
  }
  57% {
    transform: translate(0%, 100%);
  }
  71% {
    transform: translate(0%, 100%);
  }
  85% {
    transform: translate(0%, 50%);
  }
  100% {
    transform: translate(0%, 50%);
  }
}
.h3.w2.l3 {
  z-index: -3;
  animation-name: h3w2l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w2l3 {
  0% {
    transform: translate(50%, 75%);
  }
  14% {
    transform: translate(100%, 100%);
  }
  28% {
    transform: translate(100%, 100%);
  }
  43% {
    transform: translate(100%, 150%);
  }
  57% {
    transform: translate(50%, 125%);
  }
  71% {
    transform: translate(50%, 125%);
  }
  85% {
    transform: translate(50%, 75%);
  }
  100% {
    transform: translate(50%, 75%);
  }
}
.h3.w3.l1 {
  z-index: -3;
  animation-name: h3w3l1;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w3l1 {
  0% {
    transform: translate(-100%, 50%);
  }
  14% {
    transform: translate(-150%, 25%);
  }
  28% {
    transform: translate(-200%, 50%);
  }
  43% {
    transform: translate(-200%, 100%);
  }
  57% {
    transform: translate(-150%, 125%);
  }
  71% {
    transform: translate(-100%, 100%);
  }
  85% {
    transform: translate(-100%, 50%);
  }
  100% {
    transform: translate(-100%, 50%);
  }
}
.h3.w3.l2 {
  z-index: -3;
  animation-name: h3w3l2;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w3l2 {
  0% {
    transform: translate(-50%, 75%);
  }
  14% {
    transform: translate(-50%, 75%);
  }
  28% {
    transform: translate(-100%, 100%);
  }
  43% {
    transform: translate(-100%, 150%);
  }
  57% {
    transform: translate(-100%, 150%);
  }
  71% {
    transform: translate(-50%, 125%);
  }
  85% {
    transform: translate(-50%, 75%);
  }
  100% {
    transform: translate(-50%, 75%);
  }
}
.h3.w3.l3 {
  z-index: -3;
  animation-name: h3w3l3;
  animation-timing-function: ease;
  animation-duration: 3s;
  animation-iteration-count: infinite;
}

@keyframes h3w3l3 {
  0% {
    transform: translate(0%, 100%);
  }
  14% {
    transform: translate(50%, 125%);
  }
  28% {
    transform: translate(0%, 150%);
  }
  43% {
    transform: translate(0%, 200%);
  }
  57% {
    transform: translate(-50%, 175%);
  }
  71% {
    transform: translate(0%, 150%);
  }
  85% {
    transform: translate(0%, 100%);
  }
  100% {
    transform: translate(0%, 100%);
  }
}
</style>
