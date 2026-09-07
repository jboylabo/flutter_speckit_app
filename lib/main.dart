import 'package:flutter/material.dart';

import 'src/pages/anya_viewer_page.dart';

void main() {
  runApp(const AnyaApp());
}

class AnyaApp extends StatelessWidget {
  const AnyaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '3D アーニャ',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFF06292)),
      ),
      home: const AnyaViewerPage(),
    );
  }
}
