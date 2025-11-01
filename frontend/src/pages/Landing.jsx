import React from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button";
import Card from "../components/Card";

export default function Landing() {
  const features = [
    {
      icon: "📚",
      title: "Upload Tài liệu Đa dạng",
      description: "Hỗ trợ PDF, Word, Markdown và Text. Upload và quản lý tài liệu của bạn một cách dễ dàng.",
    },
    {
      icon: "🤖",
      title: "AI Hỏi Đáp Thông minh",
      description: "Đặt câu hỏi về nội dung tài liệu và nhận câu trả lời chính xác dựa trên RAG (Retrieval Augmented Generation).",
    },
    {
      icon: "🔍",
      title: "Tìm kiếm Vector Chính xác",
      description: "Sử dụng công nghệ embedding và FAISS để tìm các đoạn văn liên quan nhất trong tài liệu.",
    },
    {
      icon: "📊",
      title: "Lịch sử Hỏi Đáp",
      description: "Lưu trữ và quản lý toàn bộ lịch sử câu hỏi và câu trả lời của bạn để tham khảo sau này.",
    },
    {
      icon: "🔐",
      title: "Bảo mật Dữ liệu",
      description: "Xác thực người dùng bằng JWT, mỗi tài liệu được quản lý riêng theo tài khoản của bạn.",
    },
    {
      icon: "⚡",
      title: "Xử lý Nhanh chóng",
      description: "Công nghệ embedding và RAG hiện đại, cho phép nhận câu trả lời nhanh chóng và chính xác.",
    },
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-purple-600 via-blue-600 to-indigo-700 text-white overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 left-0 w-96 h-96 bg-white rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 right-0 w-96 h-96 bg-white rounded-full blur-3xl"></div>
        </div>
        <div className="relative container mx-auto px-4 py-20 md:py-32">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-block mb-4 px-4 py-2 bg-white/20 backdrop-blur-sm rounded-full text-sm font-medium">
              ✨ Nền tảng Học tập thông minh với AI
            </div>
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
              Transform Your Study với
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-yellow-200 to-pink-200">
                AI Intelligence
              </span>
            </h1>
            <p className="text-xl md:text-2xl text-blue-100 mb-8 max-w-2xl mx-auto leading-relaxed">
              Khai thác sức mạnh của trí tuệ nhân tạo để tự động hóa việc học tập, nhận insights từ tài liệu, 
              và tăng tốc quá trình nghiên cứu với nền tảng AI Study QnA hiện đại.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link to="/login">
                <Button className="px-8 py-4 text-lg bg-white text-purple-600 hover:bg-gray-100 font-semibold shadow-lg">
                  Bắt đầu Miễn phí →
                </Button>
              </Link>
              <Link to="/login">
                <Button variant="secondary" className="px-8 py-4 text-lg bg-white/10 backdrop-blur-sm text-white hover:bg-white/20 border border-white/30 font-semibold">
                  Đăng nhập
                </Button>
              </Link>
            </div>
            <div className="mt-12 flex flex-wrap justify-center gap-8 text-blue-100">
              <div className="text-center">
                <div className="text-3xl font-bold text-white">100%</div>
                <div className="text-sm">Miễn phí</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">∞</div>
                <div className="text-sm">Tài liệu</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">24/7</div>
                <div className="text-sm">Hỗ trợ</div>
              </div>
            </div>
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-b from-transparent to-gray-50"></div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-gray-50">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-800 mb-4">
              Tính năng Mạnh mẽ
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Khám phá cách các công cụ AI có thể cách mạng hóa quy trình học tập và tăng năng suất của bạn.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <Card key={index} className="hover:shadow-xl transition-all duration-300 hover:-translate-y-2 border border-gray-100">
                <div className="text-5xl mb-4">{feature.icon}</div>
                <h3 className="text-xl font-bold text-gray-800 mb-3">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">{feature.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-r from-purple-600 to-blue-600 text-white">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Sẵn sàng Nâng cấp Quá trình Học tập?
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Tham gia cùng hàng nghìn học sinh và sinh viên đang sử dụng nền tảng AI của chúng tôi 
            để thúc đẩy học tập và đổi mới.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/login">
              <Button className="px-8 py-4 text-lg bg-white text-purple-600 hover:bg-gray-100 font-semibold shadow-lg">
                Bắt đầu Miễn phí
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="secondary" className="px-8 py-4 text-lg bg-white/10 backdrop-blur-sm text-white hover:bg-white/20 border border-white/30 font-semibold">
                Đăng nhập
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300 py-12">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center mb-4">
                <span className="text-2xl mr-2">🧠</span>
                <span className="text-xl font-bold text-white">AI Study QnA</span>
              </div>
              <p className="text-sm text-gray-400">
                Biến đổi việc học tập với các giải pháp AI thông minh.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Sản phẩm</h4>
              <ul className="space-y-2 text-sm">
                <li><Link to="/login" className="hover:text-white transition-colors">Tính năng</Link></li>
                <li><Link to="/login" className="hover:text-white transition-colors">Giá cả</Link></li>
                <li><Link to="/login" className="hover:text-white transition-colors">API</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Công ty</h4>
              <ul className="space-y-2 text-sm">
                <li><Link to="/login" className="hover:text-white transition-colors">Về chúng tôi</Link></li>
                <li><Link to="/login" className="hover:text-white transition-colors">Blog</Link></li>
                <li><Link to="/login" className="hover:text-white transition-colors">Liên hệ</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Hỗ trợ</h4>
              <ul className="space-y-2 text-sm">
                <li><Link to="/login" className="hover:text-white transition-colors">Trung tâm trợ giúp</Link></li>
                <li><Link to="/login" className="hover:text-white transition-colors">Chính sách bảo mật</Link></li>
                <li><Link to="/login" className="hover:text-white transition-colors">Điều khoản dịch vụ</Link></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 pt-8 text-center text-sm text-gray-400">
            <p>© 2024 AI Study QnA. Tất cả quyền được bảo lưu.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

