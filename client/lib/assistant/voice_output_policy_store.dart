import 'dart:io';

import 'package:shared_preferences/shared_preferences.dart';

import 'voice_output_policy.dart';

class VoiceOutputPolicyStore {
  VoiceOutputPolicyStore({SharedPreferences? preferences})
    : _memory =
          preferences == null && Platform.environment['FLUTTER_TEST'] == 'true'
          ? <String, String>{}
          : null,
      _preferencesFuture = preferences != null
          ? Future.value(preferences)
          : (Platform.environment['FLUTTER_TEST'] == 'true'
                ? null
                : SharedPreferences.getInstance());

  VoiceOutputPolicyStore.memory()
    : _memory = <String, String>{},
      _preferencesFuture = null;

  final Map<String, String>? _memory;
  final Future<SharedPreferences>? _preferencesFuture;

  static String prefKeyForUser(String userId) => 'voice_output_policy.$userId';

  Future<VoiceOutputPolicy> load(String userId) async {
    if (userId.isEmpty) {
      return VoiceOutputPolicy.handsFreeOnly;
    }
    final memory = _memory;
    if (memory != null) {
      return decode(memory[prefKeyForUser(userId)]);
    }
    final prefs = await _preferencesFuture!;
    return decode(prefs.getString(prefKeyForUser(userId)));
  }

  Future<void> save(String userId, VoiceOutputPolicy policy) async {
    if (userId.isEmpty) {
      return;
    }
    final memory = _memory;
    if (memory != null) {
      memory[prefKeyForUser(userId)] = encode(policy);
      return;
    }
    final prefs = await _preferencesFuture!;
    await prefs.setString(prefKeyForUser(userId), encode(policy));
  }

  static String encode(VoiceOutputPolicy policy) {
    switch (policy) {
      case VoiceOutputPolicy.handsFreeOnly:
        return 'hands_free_only';
      case VoiceOutputPolicy.allVoiceInput:
        return 'all_voice_input';
      case VoiceOutputPolicy.never:
        return 'never';
    }
  }

  static VoiceOutputPolicy decode(String? raw) {
    switch (raw) {
      case 'all_voice_input':
        return VoiceOutputPolicy.allVoiceInput;
      case 'never':
        return VoiceOutputPolicy.never;
      case 'hands_free_only':
      default:
        return VoiceOutputPolicy.handsFreeOnly;
    }
  }
}
