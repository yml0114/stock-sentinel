import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/events_provider.dart';
import '../widgets/event_card.dart';

class EventsScreen extends StatefulWidget {
  const EventsScreen({super.key});

  @override
  State<EventsScreen> createState() => _EventsScreenState();
}

class _EventsScreenState extends State<EventsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<EventsProvider>().refresh(limit: 100);
      context.read<EventsProvider>().markRead();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('全部事件'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              context.read<EventsProvider>().refresh(limit: 100);
            },
          ),
        ],
      ),
      body: Consumer<EventsProvider>(
        builder: (context, provider, _) {
          if (provider.loading && provider.events.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }
          if (provider.events.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.event_note, size: 64, color: Colors.grey[700]),
                  const SizedBox(height: 16),
                  Text(
                    '暂无事件',
                    style: TextStyle(fontSize: 16, color: Colors.grey[600]),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '系统会实时监控并推送重要事件',
                    style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () => provider.refresh(limit: 100),
            child: ListView.builder(
              padding: const EdgeInsets.only(top: 8, bottom: 20),
              itemCount: provider.events.length,
              itemBuilder: (context, index) {
                return EventCard(event: provider.events[index]);
              },
            ),
          );
        },
      ),
    );
  }
}
