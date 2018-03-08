#!/usr/bin/env python

import rospy
import math

from geometry_msgs.msg import PoseStamped, TwistStamped
from styx_msgs.msg import Lane, Waypoint
from std_msgs.msg import String
from dynamic_reconfigure.server import Server
from waypoint_updater.cfg import DynReconfConfig


'''
This node will publish waypoints from the car's current position to some `x`
distance ahead.  As mentioned in the doc, you should ideally first implement
a version which does not care about traffic lights or obstacles.

Once you have created dbw_node, you will update this node to use the status of
traffic lights too.

Please note that our simulator also provides the exact location of traffic
lights and their current status in `/vehicle/traffic_lights` message. You
can use this message to build this node as well as to verify your TL
classifier.

'''


class WaypointUpdater(object):
    def __init__(self):
        self.dyn_vals_received = False
        self.waypoints = []
        self.pose = None
        self.velocity = None
        self.final_waypoints = []
        self.next_traffic_light_wp = None
        if not self.dyn_vals_received:
            self.update_rate = 3
            self.default_velocity = 0.0
            self.lookahead_wps = 50
        self.subs = {}
        self.pubs = {}

        rospy.init_node('waypoint_updater')

        self.subs['/current_pose'] = \
            rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)

        self.subs['/base_waypoints'] = \
            rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)

        self.subs['/current_velocity'] = \
            rospy.Subscriber('/current_velocity', TwistStamped,
                             self.velocity_cb)

        # TODO: Add a subscriber for /traffic_waypoint and /obstacle_waypoint
        #  self.subs['/traffic_waypoint'] = \
        #      rospy.Subscriber('/traffic_waypoint', String, self.traffic_cb)

        self.pubs['/final_waypoints'] = rospy.Publisher('/final_waypoints',
                                                        Lane, queue_size=1)

        # TODO: Add other member variables you need below
        self.dyn_reconf_srv = Server(DynReconfConfig, self.dyn_vars_cb)

        self.loop()

    def loop(self):
        self.rate = rospy.Rate(self.update_rate)
        # wait for waypoints and pose to be loaded before trying to update
        # waypoints
        while not self.waypoints:
            self.rate.sleep()
        while not self.pose:
            self.rate.sleep()
        while not rospy.is_shutdown():

            if self.waypoints:
                self.send_waypoints()
            self.rate.sleep()

    # adjust dynamic variables
    def dyn_vars_cb(self, config, level):
        if self.update_rate:
            old_update_rate = self.update_rate
            old_default_velocity = self.default_velocity
            old_lookahead_wps = self.lookahead_wps
        else:
            self.dyn_vals_received = True
            old_update_rate = 1
            old_default_velocity = 0.0
            old_lookahead_wps = 50

        rospy.loginfo("Received dynamic parameters {} with level: {}"
                      .format(config, level))

        if old_update_rate != config['dyn_update_rate']:
            rospy.loginfo("waypoint_updater:dyn_vars_cb Adjusting update Rate \
                           from {} to {}".format(old_update_rate,
                                                 config['dyn_update_rate']))
            self.update_rate = config['dyn_update_rate']
            # need to switch the delay
            self.rate = rospy.Rate(self.update_rate)

        if old_default_velocity != config['dyn_default_velocity']:
            rospy.loginfo("waypoint_updater:dyn_vars_cb Adjusting default_"
                          "velocity from {} to {}"
                          .format(old_default_velocity,
                                  config['dyn_default_velocity']))
            self.default_velocity = config['dyn_default_velocity']

        if old_lookahead_wps != config['dyn_lookahead_wps']:
            rospy.loginfo("waypoint_updater:dyn_vars_cb Adjusting lookahead_"
                          "wps from {} to {}"
                          .format(old_lookahead_wps,
                                  config['dyn_lookahead_wps']))
            self.lookahead_wps = config['dyn_lookahead_wps']

        return config

    def velocity_cb(self, twist_msg):
        self.velocity = twist_msg

    def pose_cb(self, pose_msg):
        self.pose = pose_msg.pose
        rospy.loginfo("waypoint_updater:pose_cb pose set to  %s", self.pose)
        #  self.send_waypoints()

    def waypoints_cb(self, lane_msg):
        rospy.loginfo("waypoint_updater:waypoints_cb loading waypoints")
        if not self.waypoints:
            for waypoint in lane_msg.waypoints:
                self.waypoints.append(waypoint)
            rospy.loginfo("waypoint_updater:waypoints_cb %d waypoints loaded",
                          len(self.waypoints))
        else:
            rospy.logerr("waypoint_updater:waypoints_cb attempt to load "
                         "waypoints when we have already loaded %d waypoints",
                         len(self.waypoints))

        self.subs['/base_waypoints'].unregister()
        rospy.loginfo("Unregistered from /base_waypoints topic")

    def traffic_cb(self, traffic_msg):
        # TODO: Callback for /traffic_waypoint message. Implement
        # self.next_traffic_light_wp = traffic_msg.data
        pass

    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message.
        # We will implement it later
        pass

    def send_waypoints(self):
        # generates the list of LOOKAHEAD_WPS waypoints based on car location
        # for now assume waypoints form a loop
        new_wps_list = []
        start_wps_ptr = self.closest_waypoint()
        end_wps_ptr = (start_wps_ptr +
                       self.lookahead_wps) % len(self.waypoints)
        rospy.loginfo("waypoint_updater:send_waypoints start_wps_ptr = %d,"
                      " end_wps_ptr = %d", start_wps_ptr, end_wps_ptr)
        if end_wps_ptr > start_wps_ptr:
            for w_p in self.waypoints[start_wps_ptr:end_wps_ptr]:
                w_p.twist.twist.linear.x = self.default_velocity
                new_wps_list.append(w_p)
            # end of for
        else:
            for w_p in self.waypoints[start_wps_ptr:]:
                w_p.twist.twist.linear.x = self.default_velocity
                new_wps_list.append(w_p)
            # end of for
            for w_p in self.waypoints[:end_wps_ptr]:
                w_p.twist.twist.linear.x = self.default_velocity
                new_wps_list.append(w_p)
            # end of for
        # end of if
        rospy.loginfo("waypoint_updater:send_waypoints final_waypoints list"
                      " length is %d", len(new_wps_list))
        lane = Lane()
        lane.waypoints = list(new_wps_list)
        lane.header.frame_id = '/world'
        lane.header.stamp = rospy.Time()
        self.pubs['/final_waypoints'].publish(lane)

    def get_waypoint_velocity(self, waypoint):
        return waypoint.twist.twist.linear.x

    def set_waypoint_velocity(self, waypointlist, waypoint, velocity):
        waypointlist[waypoint].twist.twist.linear.x = velocity

    def closest_waypoint(self):
        dist = 1000000  # maybe should use max
        closest = 0

        def distance_lambda(a, b): return math.sqrt(
            (a.x-b.x)**2 + (a.y-b.y)**2)
        for i in range(len(self.waypoints)):
            tmpdist = distance_lambda(self.waypoints[i].pose.pose.position,
                                      self.pose.position)
            if tmpdist < dist:
                closest = i
                dist = tmpdist
            # end of if
        # end of for
        return closest
        # TODO - implement next_waypoint to make sure we start list at a point
        # in front of the car

    def distance(self, wp1, wp2):
        dist = 0

        def distance_lambda(a, b): return math.sqrt((a.x-b.x)**2 +
                                                    (a.y-b.y)**2 +
                                                    (a.z-b.z)**2)
        for i in range(wp1, wp2+1):
            dist += distance_lambda(self.waypoints[wp1].pose.pose.position,
                                    self.waypoints[i].pose.pose.position)
            wp1 = i
        return dist


if __name__ == '__main__':
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')
