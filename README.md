# DroneContest - 空中具身智能自主导航系统

本项目为《空中具身智能赛项》量身打造的无人机底层软件架构与算法工作空间。项目基于 **ROS 1 (Noetic)** 开发，实现了从 3D 物理仿真 (Gazebo + PX4) 到自主视觉避障 (Ego-Planner-Swarm) 再到状态机决策控制 (Auto Commander) 的全链路闭环。

未来的实机硬件目标平台为：**5寸重载飞行器 + Pixhawk 6C Mini + Jetson Orin Nano + OAK-D-Pro 深度相机**。目前已完美实现 SITL (Software In The Loop) 纯软件在环仿真。

---

## 核心技术栈

* **OS**: Docker (Ubuntu 20.04)
* **Middleware**: ROS 1 Noetic
* **Flight Controller (SITL)**: PX4 Autopilot (`v1.13.3`)
* **Physics Engine**: Gazebo Classic (`iris_obs_avoid` 模型带深度相机)
* **Planning Algorithm**: Ego-Planner-Swarm (ZJU FAST Lab)

---

## 快速开始：环境配置指南

> **极其重要**：本项目代码体积轻量。为了不撑爆 GitHub 仓库，体积庞大的 PX4 源码和编译文件已被加入 `.gitignore`。拉取本项目后，**必须手动下载 PX4 并补全依赖**。

### 1. 宿主机 (Ubuntu 24.04) 准备

在克隆代码前，请确保宿主机已安装 Docker，并开放 X11 图形界面转发权限：

```bash
# 开放本地显示权限 (每次重启宿主机后必须执行一次)
xhost +local:root

```

### 2. 启动 Docker 开发舱

```bash
# 拉取包含 ROS 的 Ubuntu 20.04 镜像并挂载代码目录 (首次运行)
docker run -it \
  --name ego_docker \
  --privileged \
  --net=host \
  --env="DISPLAY=$DISPLAY" \
  --env="QT_X11_NO_MITSHM=1" \
  --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
  --volume="$HOME/ego_ws:/root/ego_ws:rw" \
  osrf/ros:noetic-desktop-full \
  /bin/bash

```

### 3. 克隆代码与补全第三方库 (在 Docker 终端内执行)

```bash
# 1. 克隆本项目代码
cd /root
git clone https://github.com/Wunicheng233/DroneContest.git ego_ws
cd /root/ego_ws

# 2. 补充下载核心规划算法 (Ego-Planner-Swarm)
mkdir -p src && cd src
git clone https://github.com/ZJU-FAST-Lab/ego-planner-swarm.git
cd ..

# 3. 补充下载飞控源码 (必须是 v1.13.3 稳定版)
git clone https://github.com/PX4/PX4-Autopilot.git -b v1.13.3 --recursive

# 4. 安装核心编译依赖
sudo apt-get update
sudo apt install -y ros-noetic-mavros ros-noetic-mavros-extras libarmadillo-dev ros-noetic-nlopt
# 下载 MAVROS 地理数据集 (必装，防止跳红字)
wget -O - https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh | sudo bash

```

### 4. 编译与环境变量注册

```bash
# 编译 ROS 工作空间
cd /root/ego_ws
catkin_make -j4

# 将工作空间和 PX4 路径永久写入 ~/.bashrc
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
echo "source /root/ego_ws/devel/setup.bash" >> ~/.bashrc
echo "source /root/ego_ws/PX4-Autopilot/Tools/setup_gazebo.bash /root/ego_ws/PX4-Autopilot /root/ego_ws/PX4-Autopilot/build/px4_sitl_default" >> ~/.bashrc
echo "export ROS_PACKAGE_PATH=\$ROS_PACKAGE_PATH:/root/ego_ws/PX4-Autopilot:/root/ego_ws/PX4-Autopilot/Tools/sitl_gazebo" >> ~/.bashrc

source ~/.bashrc

```

---

## 仿真运行指南 (5 终端终极联调)

请在 Docker 内部打开 5 个独立的终端窗口，严格按以下顺序执行：

**终端 1：启动 3D 物理世界与飞控小脑**

```bash
roslaunch px4 mavros_posix_sitl.launch vehicle:=iris_obs_avoid
# 等待 Gazebo 弹出，并确认终端刷出 `Got HEARTBEAT`

```

**终端 2：解除飞控安全封印 (极其关键)**
*由于 Ego-Planner 的外部接管逻辑与 PX4 默认的避障/遥控器保护冲突，起飞前必须通过 MAVROS 动态关闭底层保护参数。*

```bash
rosrun mavros mavparam set COM_OBS_AVOID 0
rosrun mavros mavparam set NAV_RCL_ACT 0
rosrun mavros mavparam set NAV_DLL_ACT 0
rosrun mavros mavparam set COM_RCL_EXCEPT 4
# 执行完毕后，此终端可复用

```

**终端 3：启动神经翻译官 (Ego PX4 Bridge)**
*负责高频发布 1.5 米悬停指令进行 `OFFBOARD` 保活，并将 Ego-Planner 生成的 3D 彩色轨迹翻译为飞控可识别的控制集。*

```bash
python3 /root/ego_ws/src/ego_px4_bridge.py
# 确认终端持续打印保活心跳日志

```

**终端 4：唤醒视觉避障大脑 (Ego-Planner)**

```bash
roslaunch ego_planner single_run_in_sim.launch
# RViz 3D 可视化界面将自动弹出，显示深度点云与机器位姿

```

**终端 5：启动最高战术指挥官 & 一键点火**
*执行自主起飞、悬停侦测、战术点发送等连贯状态机动作。*

```bash
# 启动战术状态机监听
python3 /root/ego_ws/src/auto_commander.py

# 在任意空闲终端执行最终点火指令 (切入外部接管模式并解锁电机)
rosrun mavros mavsys mode -c OFFBOARD
rosrun mavros mavsafety arm

```

*(点火后，请放开鼠标键盘，在 Gazebo 和 RViz 中欣赏无人机全自动升空、巡航并穿透虚拟得分环的华丽操作！)*