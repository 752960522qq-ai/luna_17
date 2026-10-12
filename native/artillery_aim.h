#pragma once
static int bte_artillery_reachable(BteVec direction,BteVec forward,BteVec right,float traverse,float elevation,float depression){
 float yaw=atan2f(bte_dot(direction,right),bte_dot(direction,forward))*57.2957795f;
 float pitch=atan2f(direction.y,sqrtf(direction.x*direction.x+direction.z*direction.z))*57.2957795f;
 return fabsf(yaw)<=traverse+.01f&&pitch<=elevation+.01f&&pitch>=-depression-.01f;
}
