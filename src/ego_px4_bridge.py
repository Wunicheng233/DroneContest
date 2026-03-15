#!/usr/bin/env python3
import rospy
from quadrotor_msgs.msg import PositionCommand
from mavros_msgs.msg import PositionTarget

class EgoPX4Bridge:
    def __init__(self):
        rospy.init_node('ego_px4_bridge')
        self.pub_setpoint = rospy.Publisher('/mavros/setpoint_raw/local', PositionTarget, queue_size=1)
        rospy.Subscriber('/drone_0_planning/pos_cmd', PositionCommand, self.cmd_cb, queue_size=1)
        
        self.has_ego_cmd = False
        self.ego_pt = PositionTarget()
        rospy.Timer(rospy.Duration(0.02), self.timer_cb)

    def cmd_cb(self, msg):
        self.has_ego_cmd = True
        pt = PositionTarget()
        pt.header.frame_id = "map"  # 💥 补丁1：加上坐标系，防止 MAVROS 丢包
        pt.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        pt.type_mask = (PositionTarget.IGNORE_AFX | PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ | PositionTarget.IGNORE_YAW_RATE)
        pt.position.x = msg.position.x
        pt.position.y = msg.position.y
        pt.position.z = msg.position.z
        pt.velocity.x = msg.velocity.x
        pt.velocity.y = msg.velocity.y
        pt.velocity.z = msg.velocity.z
        pt.yaw = msg.yaw
        self.ego_pt = pt

    def timer_cb(self, event):
        if self.has_ego_cmd:
            self.ego_pt.header.stamp = rospy.Time.now() # 💥 补丁2：实时刷新时间戳！
            self.pub_setpoint.publish(self.ego_pt)
            speed = abs(self.ego_pt.velocity.x) + abs(self.ego_pt.velocity.y) + abs(self.ego_pt.velocity.z)
            if speed > 0.05:
                rospy.loginfo_throttle(1.0, "🚀 【Ego大脑】正在全速避障飞行中！")
            else:
                rospy.loginfo_throttle(2.0, "✅ 【Ego大脑】已到达目标，正在精准悬停...")
        else:
            pt = PositionTarget()
            pt.header.stamp = rospy.Time.now()
            pt.header.frame_id = "map"
            pt.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
            pt.type_mask = (PositionTarget.IGNORE_VX | PositionTarget.IGNORE_VY | PositionTarget.IGNORE_VZ | 
                            PositionTarget.IGNORE_AFX | PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ | 
                            PositionTarget.IGNORE_YAW_RATE)
            pt.position.x = 0.0
            pt.position.y = 0.0
            pt.position.z = 1.5  # 持续发送1.5米安全高度
            pt.yaw = 0.0
            self.pub_setpoint.publish(pt)
            rospy.loginfo_throttle(1.0, "【翻译官】持续发送 1.5m 悬停包，保活 OFFBOARD...")

if __name__ == '__main__':
    try:
        bridge = EgoPX4Bridge()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass