#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import math
from geometry_msgs.msg import PoseStamped

class AutoCommander:
    def __init__(self):
        rospy.init_node('auto_commander')

        # 1. 发布者：给 Ego-Planner 发送目标点
        self.goal_pub = rospy.Publisher('/move_base_simple/goal', PoseStamped, queue_size=1)

        # 2. 订阅者：听取飞控当前的位置，用来判断“我们飞到地方没？”
        rospy.Subscriber('/mavros/local_position/pose', PoseStamped, self.pose_cb, queue_size=1)

        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.has_pose = False

        # 【核心逻辑：定义战术状态】
        self.STATE_WAITING = 0      # 状态 0: 趴在地上，等待起飞
        self.STATE_EXPLORING = 1    # 状态 1: 飞向圆环前的“预备观测点”
        self.STATE_SEARCHING = 2    # 状态 2: 悬停开启相机，寻找圆环
        self.STATE_CROSSING = 3     # 状态 3: 视觉锁定圆环！全速穿刺！
        self.STATE_FINISHED = 4     # 状态 4: 穿环完成，任务结束
        
        self.state = self.STATE_WAITING
        self.target_goal = None
        self.search_start_time = None

        # 战术循环：大脑以 10Hz 的频率，高速运转状态机
        rospy.Timer(rospy.Duration(0.1), self.control_loop)
        rospy.loginfo("👑 【最高指挥官】已上线！死死盯住无人机高度，等待起飞...")

    def pose_cb(self, msg):
        self.current_x = msg.pose.position.x
        self.current_y = msg.pose.position.y
        self.current_z = msg.pose.position.z
        self.has_pose = True

    def send_goal(self, x, y, z):
        # 将传入的 XYZ 坐标打包成 Ego-Planner 听得懂的话题并发射
        goal = PoseStamped()
        goal.header.stamp = rospy.Time.now()
        goal.header.frame_id = "world"  
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.position.z = z
        goal.pose.orientation.w = 1.0
        self.goal_pub.publish(goal)
        self.target_goal = (x, y, z)
        rospy.logwarn(f"🎯 [指挥官下令] 坐标: X={x}, Y={y}, Z={z}")

    def distance_to_target(self):
        # 勾股定理算三维空间误差距离
        if not self.target_goal: return 999.0
        dx = self.current_x - self.target_goal[0]
        dy = self.current_y - self.target_goal[1]
        dz = self.current_z - self.target_goal[2]
        return math.sqrt(dx**2 + dy**2 + dz**2)

    def control_loop(self, event):
        if not self.has_pose: return

        # ==========================================
        # 状态 0: 敏锐的起飞嗅觉
        # ==========================================
        if self.state == self.STATE_WAITING:
            # 只要无人机高度超过 1.0 米，立刻判定起飞成功，接管比赛！
            if self.current_z > 1.0:  
                rospy.loginfo("✅ [指挥官] 检测到成功起飞并悬停！3秒后切入【探索寻环模式】")
                rospy.sleep(3.0) 
                self.send_goal(3.0, 0.0, 1.5)  # 先往前飞 3 米作为观测点
                self.state = self.STATE_EXPLORING

        # ==========================================
        # 状态 1: 飞向预备观测点
        # ==========================================
        elif self.state == self.STATE_EXPLORING:
            # 距离目标不到 0.3 米，认为已经就位
            if self.distance_to_target() < 0.3:  
                rospy.loginfo("🔍 [指挥官] 到达预备点！开启相机，假装正在运行 YOLO 寻找圆环...")
                self.search_start_time = rospy.Time.now()
                self.state = self.STATE_SEARCHING

        # ==========================================
        # 状态 2: 视觉瞄准 (这里用延时模拟 YOLO 的运算时间)
        # ==========================================
        elif self.state == self.STATE_SEARCHING:
            if (rospy.Time.now() - self.search_start_time).to_sec() > 2.0:
                
                # 💥【比赛最核心的穿环战术】：
                # 我们假设真实的圆环在前方 X=5.0 的位置。
                # 战术欺骗：我们必须把目标点定在圆环的“正后方” X=7.0！
                rospy.loginfo("🚀 [指挥官] 视觉锁定得分环！战术欺骗启动，发起穿环冲锋！")
                self.send_goal(7.0, 0.0, 1.5)
                self.state = self.STATE_CROSSING

        # ==========================================
        # 状态 3: 监控穿环突进过程
        # ==========================================
        elif self.state == self.STATE_CROSSING:
            if self.distance_to_target() < 0.4:
                rospy.loginfo("🎉 [指挥官] 穿环突进成功！任务圆满完成，切入驻留状态。")
                self.state = self.STATE_FINISHED

        # ==========================================
        # 状态 4: 任务结束，原地挂机
        # ==========================================
        elif self.state == self.STATE_FINISHED:
            pass # 啥也不干，底层的 ego_px4_bridge 会自动接管实现原地死死悬停

if __name__ == '__main__':
    try:
        AutoCommander()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass