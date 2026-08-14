import { redirect } from "next/navigation";

/** 原小红绿书入口改到书籍剪辑 */
export default function XiaohonglvshuRedirect() {
  redirect("/book");
}
