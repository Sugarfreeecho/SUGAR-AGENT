declare module 'virtual:sugaragent-smooth-follow' {
  export function createSmoothFollowController():any;
  export function computeSmoothRevealCount(backlog:number,dtMs:number):number;
  export function takeSmoothTextPrefix(text:string,count:number):{segment:string;rest:string;count:number};
}
