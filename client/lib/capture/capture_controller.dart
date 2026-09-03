import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/voice_recorder.dart';
import '../assistant/voice_temp_files.dart';
import '../auth/auth_controller.dart';
import '../voice/voice_transcription_controller.dart';
import 'capture_draft.dart';
import 'capture_mode.dart';
import 'capture_url.dart';

enum CaptureSubmitState {
  idle,
  submitting,
  success,
  validationError,
  authError,
  networkError,
  serverError,
}

class CaptureController extends ChangeNotifier {
  CaptureController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    CaptureDraft? initialDraft,
    VoiceRecorder? voiceRecorder,
    VoiceTempFiles? voiceTempFiles,
    VoiceTranscriptionController? voiceController,
    CaptureMode initialMode = CaptureMode.note,
  })  : _apiClient = apiClient,
        _authController = authController,
        _draft = initialDraft ?? CaptureDraft.empty,
        _mode = initialMode,
        _voice = voiceController ??
            VoiceTranscriptionController(
              apiClient: apiClient,
              authController: authController,
              voiceRecorder: voiceRecorder,
              voiceTempFiles: voiceTempFiles,
            ) {
    _voice.bindTranscriptConsumer(_handleVoiceTranscript);
    _voice.addListener(_onVoiceChanged);
  }

  final SecretaryApiClient _apiClient;
  final AuthController _authController;
  final VoiceTranscriptionController _voice;

  CaptureDraft _draft;
  CaptureMode _mode;
  CaptureSubmitState submitState = CaptureSubmitState.idle;
  CaptureSubmitKind? lastSubmitKind;
  String? errorMessage;
  CaptureTaskResponse? lastTaskResult;
  CaptureNoteResponse? lastNoteResult;
  IntakeLinkResult? lastLinkResult;

  CaptureTaskResponse? get lastResult => lastTaskResult;

  VoiceState get voiceState => _voice.voiceState;
  String? get voiceErrorMessage => _voice.voiceErrorMessage;
  bool get isVoiceBusy => _voice.isVoiceBusy;

  CaptureDraft get draft => _draft;
  CaptureMode get mode => _mode;

  bool get isExactLinkInput => isExactHttpUrl(_draft.text);

  String get primaryActionLabel {
    if (isExactLinkInput) {
      return 'Добавить ссылку';
    }
    return _mode == CaptureMode.task ? 'Создать задачу' : 'Добавить заметку';
  }

  void _onVoiceChanged() {
    notifyListeners();
  }

  void setMode(CaptureMode mode) {
    _mode = mode;
    if (submitState != CaptureSubmitState.submitting) {
      submitState = CaptureSubmitState.idle;
      errorMessage = null;
    }
    notifyListeners();
  }

  void setText(String value) {
    _draft = _draft.copyWith(text: value);
    if (submitState != CaptureSubmitState.submitting) {
      submitState = CaptureSubmitState.idle;
      errorMessage = null;
    }
    notifyListeners();
  }

  void setTitle(String? value) {
    final trimmed = value?.trim();
    _draft = trimmed == null || trimmed.isEmpty
        ? _draft.copyWith(clearTitle: true)
        : _draft.copyWith(title: value);
    if (submitState != CaptureSubmitState.submitting) {
      submitState = CaptureSubmitState.idle;
      errorMessage = null;
    }
    notifyListeners();
  }

  void appendTranscriptToText(String transcript) {
    final trimmed = transcript.trim();
    if (trimmed.isEmpty) {
      return;
    }
    final current = _draft.text;
    if (current.isEmpty) {
      setText(trimmed);
    } else {
      setText('$current $trimmed');
    }
  }

  void mergeDraft(CaptureDraft draft) {
    _draft = draft;
    submitState = CaptureSubmitState.idle;
    errorMessage = null;
    notifyListeners();
  }

  void attachContext(CaptureContextRef ref) {
    final ids = List<String>.from(_draft.contextObjectIds);
    final refs = List<CaptureContextRef>.from(_draft.contextRefs);
    if (!ids.contains(ref.id)) {
      ids.add(ref.id);
      refs.add(ref);
    } else {
      final index = ids.indexOf(ref.id);
      refs[index] = ref;
    }
    _draft = _draft.copyWith(contextObjectIds: ids, contextRefs: refs);
    if (submitState != CaptureSubmitState.submitting) {
      submitState = CaptureSubmitState.idle;
      errorMessage = null;
    }
    notifyListeners();
  }

  void attachObjectContext(SecretaryObject object) {
    attachContext(
      CaptureContextRef(
        id: object.id,
        title: object.title,
        kind: object.kind,
      ),
    );
  }

  Future<void> startVoiceRecording() async {
    if (submitState == CaptureSubmitState.submitting || isVoiceBusy) {
      return;
    }
    if (voiceState == VoiceState.error) {
      clearVoiceError();
    }
    await _voice.startRecording();
  }

  Future<void> stopVoiceRecordingAndTranscribe() async {
    await _voice.stopAndTranscribe();
  }

  Future<void> _handleVoiceTranscript(String transcript) async {
    appendTranscriptToText(transcript);
  }

  Future<void> cancelVoiceRecording() async {
    await _voice.cancel();
  }

  void clearVoiceError() {
    _voice.clearError();
  }

  Future<void> submit() async {
    if (!_draft.canSubmit || submitState == CaptureSubmitState.submitting) {
      if (_draft.isBlank) {
        submitState = CaptureSubmitState.validationError;
        errorMessage = 'Text cannot be blank.';
        notifyListeners();
      }
      return;
    }

    final trimmed = _draft.text.trim();
    if (isExactHttpUrl(trimmed)) {
      await _submitLink(trimmed);
      return;
    }
    if (_mode == CaptureMode.task) {
      await _submitTask();
    } else {
      await _submitNote();
    }
  }

  Future<void> _submitTask() async {
    submitState = CaptureSubmitState.submitting;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _apiClient.captureTask(_draft.toRequest());
      lastTaskResult = result;
      lastNoteResult = null;
      lastLinkResult = null;
      lastSubmitKind = CaptureSubmitKind.task;
      _draft = CaptureDraft.empty;
      submitState = CaptureSubmitState.success;
      notifyListeners();
    } on AuthenticationException catch (e) {
      submitState = CaptureSubmitState.authError;
      errorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on ValidationException catch (e) {
      _fail(e.message, CaptureSubmitState.validationError);
    } on NetworkException catch (e) {
      _fail(e.message, CaptureSubmitState.networkError);
    } on ApiException catch (e) {
      _fail(e.message, CaptureSubmitState.serverError);
    }
  }

  Future<void> _submitNote() async {
    submitState = CaptureSubmitState.submitting;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _apiClient.captureNote(_draft.toNoteRequest());
      lastNoteResult = result;
      lastTaskResult = null;
      lastLinkResult = null;
      lastSubmitKind = CaptureSubmitKind.note;
      _draft = CaptureDraft.empty;
      submitState = CaptureSubmitState.success;
      notifyListeners();
    } on AuthenticationException catch (e) {
      submitState = CaptureSubmitState.authError;
      errorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on ValidationException catch (e) {
      _fail(e.message, CaptureSubmitState.validationError);
    } on NetworkException catch (e) {
      _fail(e.message, CaptureSubmitState.networkError);
    } on ApiException catch (e) {
      _fail(e.message, CaptureSubmitState.serverError);
    }
  }

  Future<void> _submitLink(String url) async {
    submitState = CaptureSubmitState.submitting;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _apiClient.intakeLink(url);
      lastLinkResult = result;
      lastTaskResult = null;
      lastNoteResult = null;
      lastSubmitKind = CaptureSubmitKind.link;
      _draft = CaptureDraft.empty;
      submitState = CaptureSubmitState.success;
      notifyListeners();
    } on AuthenticationException catch (e) {
      submitState = CaptureSubmitState.authError;
      errorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on ValidationException catch (e) {
      _fail(e.message, CaptureSubmitState.validationError);
    } on NetworkException catch (e) {
      _fail(e.message, CaptureSubmitState.networkError);
    } on ApiException catch (e) {
      _fail(e.message, CaptureSubmitState.serverError);
    }
  }

  void _fail(String message, CaptureSubmitState state) {
    submitState = state;
    errorMessage = message;
    notifyListeners();
  }

  void clearSuccess() {
    if (submitState == CaptureSubmitState.success) {
      submitState = CaptureSubmitState.idle;
      lastSubmitKind = null;
      notifyListeners();
    }
  }

  void resetSession() {
    _voice.reset();
    _draft = CaptureDraft.empty;
    _mode = CaptureMode.note;
    submitState = CaptureSubmitState.idle;
    errorMessage = null;
    lastTaskResult = null;
    lastNoteResult = null;
    lastLinkResult = null;
    lastSubmitKind = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _voice.removeListener(_onVoiceChanged);
    _voice.dispose();
    super.dispose();
  }
}
